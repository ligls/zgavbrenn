#!/usr/bin/env python3
"""
Local web server for the Closed Lost renewal workbench.

    python3 server/server.py [--port 8765] [--data-dir data]

* ``GET  /api/opportunities``        the imported dataset (data/opportunities.json)
* ``GET  /api/edits``                every saved edit, keyed by row hash
* ``PUT  /api/edits/<row_hash>``     upsert one edit (status, notes, overrides, follow-up)
* ``DELETE /api/edits/<row_hash>``   remove an edit (back to the parsed values)
* everything else                    the built React app in frontend/dist (SPA fallback)

Edits live in the ``edits`` table of data/closed_lost.sqlite, next to the
imported data.  The importer never drops that table, so work survives
re-imports.  Nothing here talks to the network: it binds to 127.0.0.1.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from flask import Flask, Response, abort, jsonify, request, send_from_directory

HERE = Path(__file__).resolve().parent
PROJECT_DIR = HERE.parent
DEFAULT_DATA_DIR = PROJECT_DIR / "data"
DIST_DIR = PROJECT_DIR / "frontend" / "dist"

STATUSES = ["Not started", "Called", "Left voicemail", "Callback scheduled", "Not interested", "Won back"]
LINE_TYPES = ["MP", "WLS", "Both", "Unknown"]

EDITS_SCHEMA = """
CREATE TABLE IF NOT EXISTS edits (
    row_hash            TEXT PRIMARY KEY,
    line_count_override INTEGER,
    line_type_override  TEXT,
    status              TEXT NOT NULL DEFAULT 'Not started',
    notes               TEXT NOT NULL DEFAULT '',
    follow_up_date      TEXT,
    updated_at          TEXT NOT NULL
);
"""


def create_app(data_dir: Path) -> Flask:
    app = Flask(__name__, static_folder=None)
    json_path = data_dir / "opportunities.json"
    db_path = data_dir / "closed_lost.sqlite"
    cache: dict = {"mtime": None, "payload": None, "by_id": {}}

    # ---------------------------------------------------------------- data
    def load_dataset() -> dict:
        if not json_path.exists():
            abort(503, description=f"{json_path} not found - run the importer first (make import).")
        mtime = json_path.stat().st_mtime
        if cache["mtime"] != mtime:
            with open(json_path, encoding="utf-8") as fh:
                payload = json.load(fh)
            cache.update(mtime=mtime, payload=payload,
                         by_id={o["id"]: o for o in payload["opportunities"]})
        return cache["payload"]

    def db() -> sqlite3.Connection:
        data_dir.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        con.executescript(EDITS_SCHEMA)
        return con

    def row_to_edit(row: sqlite3.Row) -> dict:
        return {
            "row_hash": row["row_hash"],
            "line_count_override": row["line_count_override"],
            "line_type_override": row["line_type_override"],
            "status": row["status"],
            "notes": row["notes"],
            "follow_up_date": row["follow_up_date"],
            "updated_at": row["updated_at"],
        }

    # ---------------------------------------------------------------- API
    @app.get("/api/opportunities")
    def api_opportunities():
        payload = load_dataset()
        resp = jsonify(payload)
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.get("/api/edits")
    def api_edits():
        con = db()
        try:
            rows = con.execute("SELECT * FROM edits").fetchall()
        finally:
            con.close()
        return jsonify({r["row_hash"]: row_to_edit(r) for r in rows})

    @app.put("/api/edits/<row_hash>")
    def api_put_edit(row_hash: str):
        body = request.get_json(force=True, silent=True) or {}

        status = body.get("status") or "Not started"
        if status not in STATUSES:
            abort(400, description=f"status must be one of {STATUSES}")
        ltype = body.get("line_type_override")
        if ltype not in (None, "") and ltype not in LINE_TYPES:
            abort(400, description=f"line_type_override must be one of {LINE_TYPES}")
        count = body.get("line_count_override")
        if count in ("", None):
            count = None
        else:
            try:
                count = int(count)
            except (TypeError, ValueError):
                abort(400, description="line_count_override must be an integer")
            if count < 0 or count > 100000:
                abort(400, description="line_count_override out of range")
        follow_up = body.get("follow_up_date") or None
        if follow_up:
            try:
                datetime.strptime(follow_up, "%Y-%m-%d")
            except ValueError:
                abort(400, description="follow_up_date must be YYYY-MM-DD")
        notes = str(body.get("notes") or "")
        now = datetime.now().isoformat(timespec="seconds")

        con = db()
        try:
            con.execute(
                """INSERT INTO edits (row_hash, line_count_override, line_type_override, status, notes, follow_up_date, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(row_hash) DO UPDATE SET
                     line_count_override = excluded.line_count_override,
                     line_type_override  = excluded.line_type_override,
                     status              = excluded.status,
                     notes               = excluded.notes,
                     follow_up_date      = excluded.follow_up_date,
                     updated_at          = excluded.updated_at""",
                (row_hash, count, ltype or None, status, notes, follow_up, now),
            )
            con.commit()
            row = con.execute("SELECT * FROM edits WHERE row_hash = ?", (row_hash,)).fetchone()
        finally:
            con.close()
        return jsonify(row_to_edit(row))

    @app.delete("/api/edits/<row_hash>")
    def api_delete_edit(row_hash: str):
        con = db()
        try:
            con.execute("DELETE FROM edits WHERE row_hash = ?", (row_hash,))
            con.commit()
        finally:
            con.close()
        return jsonify({"deleted": row_hash})

    @app.get("/api/health")
    def api_health():
        return jsonify({"ok": True, "data": json_path.exists(), "dist": (DIST_DIR / "index.html").exists()})

    # ---------------------------------------------------------------- SPA
    @app.get("/", defaults={"path": ""})
    @app.get("/<path:path>")
    def spa(path: str):
        if path.startswith("api/"):
            abort(404)
        target = DIST_DIR / path
        if path and target.is_file():
            return send_from_directory(DIST_DIR, path)
        index = DIST_DIR / "index.html"
        if not index.exists():
            return Response(
                "<h1>Front end not built</h1><p>Run <code>make build</code> (or <code>cd frontend && npm install && npm run build</code>), "
                "or use <code>make dev</code> for the Vite dev server.</p>",
                status=503, mimetype="text/html",
            )
        return send_from_directory(DIST_DIR, "index.html")

    @app.errorhandler(400)
    @app.errorhandler(404)
    @app.errorhandler(503)
    def json_error(err):
        if request.path.startswith("/api/"):
            return jsonify({"error": getattr(err, "description", str(err))}), err.code
        return err

    return app


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    app = create_app(Path(args.data_dir))
    print(f"Closed Lost workbench -> http://{args.host}:{args.port}/   (data: {args.data_dir})")
    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)


if __name__ == "__main__":
    main()
