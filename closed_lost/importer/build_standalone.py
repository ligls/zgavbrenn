#!/usr/bin/env python3
"""
Build the single-file version of the workbench.

    python3 importer/build_standalone.py [--out data/Closed_Lost_Workbench.html]

Takes the inlined front end produced by ``npm run build:standalone``
(``frontend/dist-standalone/index.html``), embeds ``data/opportunities.json``
(gzip + base64) plus any edits already saved in ``data/closed_lost.sqlite``,
and writes one HTML file that works from a double-click (file://), with no
server.  Edits made in that file live in the browser's localStorage and can
be saved to / loaded from JSON files from the app's "edits" menu.
"""

from __future__ import annotations

import argparse
import base64
import gzip
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_DIR = HERE.parent
DATA_DIR = PROJECT_DIR / "data"
DIST_HTML = PROJECT_DIR / "frontend" / "dist-standalone" / "index.html"
PLACEHOLDER_OPEN = '<script id="cl-data" type="application/gzip+base64">'


def load_edits(db_path: Path) -> list[dict]:
    if not db_path.exists():
        return []
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute("SELECT * FROM edits").fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        con.close()
    return [dict(r) for r in rows]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=str(DATA_DIR / "opportunities.json"))
    ap.add_argument("--db", default=str(DATA_DIR / "closed_lost.sqlite"))
    ap.add_argument("--html", default=str(DIST_HTML), help="inlined index.html from npm run build:standalone")
    ap.add_argument("--out", default=str(DATA_DIR / "Closed_Lost_Workbench.html"))
    ap.add_argument("--no-edits", action="store_true", help="do not embed the edits saved in SQLite")
    args = ap.parse_args()

    data_path, html_path, out_path = Path(args.data), Path(args.html), Path(args.out)
    if not data_path.exists():
        sys.exit(f"{data_path} not found - run the importer first (make import).")
    if not html_path.exists():
        sys.exit(f"{html_path} not found - run `npm run build:standalone` in frontend/ first (make standalone does both).")

    payload = json.loads(data_path.read_text(encoding="utf-8"))
    edits = [] if args.no_edits else load_edits(Path(args.db))
    payload["initial_edits"] = edits
    payload["meta"]["standalone_built_at"] = datetime.now().isoformat(timespec="seconds")

    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    blob = base64.b64encode(gzip.compress(raw, compresslevel=9)).decode("ascii")

    html = html_path.read_text(encoding="utf-8")
    start = html.find(PLACEHOLDER_OPEN)
    if start < 0:
        sys.exit("Placeholder <script id=\"cl-data\"> not found in the built HTML.")
    end = html.find("</script>", start)
    html = html[: start + len(PLACEHOLDER_OPEN)] + blob + html[end:]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"Embedded {payload['meta']['row_count']:,} opportunities ({len(raw) / 1e6:.1f} MB JSON -> {len(blob) / 1e6:.1f} MB compressed) "
          f"and {len(edits)} saved edit(s).")
    print(f"Wrote {out_path} ({out_path.stat().st_size / 1e6:.1f} MB). Open it by double-clicking.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
