# Closed Lost renewals workbench

Local, offline web app to browse, filter and work the ~5,490 TELUS SBS
opportunities marked **Closed Lost in Q4 2024** (Salesforce export).  Telecom
contracts run ~24 months, so these accounts come up for renewal in **Q4 2026**.

* **Importer** (`importer/`, Python + openpyxl): cleans the xlsx, repairs
  mojibake, parses line counts/types, computes renewal dates and contract-end
  hints, writes `data/opportunities.json` + `data/closed_lost.sqlite`, prints a
  validation report.
* **Server** (`server/server.py`, Flask, optional): serves the data, persists
  your edits (status, notes, follow-up, overrides) in SQLite and serves the
  built front end.  Binds to 127.0.0.1 only.
* **Front end** (`frontend/`, React + Vite + TypeScript): dashboard, filters,
  virtualised card/table views, detail drawer with editing, CSV/XLSX export
  (built in the browser).  Also ships as a **single self-contained HTML file**
  (`make standalone`) that needs no server at all.

Nothing talks to the network at run time.  The xlsx, `data/` and the built
`dist/` are git-ignored (the export is confidential).

## Setup (once)

```bash
cd closed_lost
make install            # pip install -r requirements.txt && npm install (in frontend/)
```

Python 3.10+ and Node 18+ are required.

## 1. Import

Put the Salesforce export anywhere (by default the newest
`Closed_Lost*.xlsx` in the repo root, in `closed_lost/` or in `closed_lost/data/`
is picked up) and run:

```bash
make import
# or: python3 importer/import_data.py path/to/Closed_Lost_Q4_2024-....xlsx
```

By default, renewal opportunities are dropped at import: any Opportunity Name
containing **renew** (renewal, renewals, renew, renewed), the typo **renwal**,
or the abbreviations **RNW / RNWL / RNWLS** (case-insensitive).  This is the
`EXCLUDE` regex in the Makefile, passed as `--exclude-name`.  Use
`make import EXCLUDE=` to keep every row, or `EXCLUDE=renewal` for the plain
word only.  The excluded count is shown in the report and in the app's subtitle.

The importer prints a validation report (also saved to `data/import_report.txt`):
row count, skipped metadata/footer rows, repaired names, extraction-source
split (name / Additional Info / none), type and bucket distributions, and 20
random rows showing the original text next to the parsed count/type.

Re-importing replaces the `opportunities` table and JSON but **never touches
the `edits` table**, so your statuses, notes and overrides survive.  Edits are
keyed on a stable hash of owner + account name + opportunity name + close date
(raw values), so they re-attach to the same rows after a fresh export.

## 2a. Single HTML file (no server)

```bash
make standalone         # -> data/Closed_Lost_Workbench.html
```

Builds an inlined front end and embeds the imported data (compressed) into one
HTML file you can open by double-clicking.  Everything works offline from
`file://`: filters, cards/table, the detail drawer, CSV and Excel export.

Edits made in that file (status, notes, follow-up, overrides) are stored in
the browser's local storage for that file.  The **"N edits"** menu in the
header lets you **save them to a JSON file**, **load/merge a JSON file**
(newest edit per row wins), and in Chrome/Edge **auto-save to a file** for the
session.  Any edits already in `data/closed_lost.sqlite` when you build are
embedded as a starting point.  Rebuilding the file after a new import keeps
your edits because they are keyed on the stable row hash.

## 2b. Run with the server

```bash
make run                # builds frontend/dist if missing, then http://127.0.0.1:8765
```

For development with hot reload: `make dev` (Flask on :8765 + Vite on :5173,
which proxies `/api`).  `make build` rebuilds `frontend/dist` after front-end
changes; `make standalone` rebuilds the single file.  `make test` runs the
parser / repair / hint unit tests.

## What the app does

**Header** – "X of 5,490" at all times, one-click *Clear filters*, sort key +
direction, Cards/Table toggle, CSV/Excel export of the current filtered view
(including your status, notes and follow-up), dashboard toggle, light/dark theme.

**Dashboard strip** – opportunities shown, Unknown-count total, sum of known
lines, worked count, contract-end hints; bar charts by bucket, by type and by
close month.  Click a bar to toggle that filter.

**Filters (combinable)** – accent-insensitive free text across account,
opportunity name, Additional Info, owner, phone (digits too) and your notes;
line-count bucket (multi-select with live counts); line type; opportunity owner
(searchable multi-select, ~650 owners); close month; estimated renewal month;
work status; follow-up due; has phone / has Additional Info / has contract-end
hint.  Counts next to each option reflect every *other* active filter.

**Cards / Table** – both virtualised (5k+ rows stay fast).  Every source
column is shown (owner, account, phone as a `tel:` link, opportunity name,
close date, next step, full Additional Info) plus the derived fields (count,
type, bucket, estimated renewal, contract-end hint, matched snippet + source).
Unknown-count rows carry an amber flag and a left border so you can fix them.

**Detail drawer** (click a card/row) – all fields, raw vs repaired names, the
parser's matched text, and the *Your work* form: line count / type override,
status (Not started · Called · Left voicemail · Callback scheduled · Not
interested · Won back), notes, follow-up date.  *Save & next* walks the
filtered list; ← / → and Esc work on the keyboard.  Overrides change the
effective count/type/bucket used by filters, sorting, charts and exports.

## Derived fields

| Field | Meaning |
|---|---|
| `line_count`, `line_type` | from `importer/line_parser.py`, Opportunity Name first, then Additional Info |
| `mp_count`, `wls_count` | per-type counts when both appear ("2 MP + 3 WLS" → 2 / 3, total 5) |
| `types_mentioned` | every MP/WLS token seen, even without a number |
| `extraction_source` | `name` / `additional_info` / `none` |
| `line_match` | the exact matched substring(s), for auditing |
| `line_bucket` | 1 … 20, 21-25, 26-30, 31+, Unknown |
| `close_month` | 2024-10 / 2024-11 / 2024-12 |
| `estimated_renewal_date` | close date + 24 months |
| `contract_end_hint` / `contract_end_month` / `contract_end_confidence` | explicit contract-end mention in Additional Info (FR/EN month names, "fin de contrat", "end of contract", "renouvellement", "renewal", "expire", …); `high` = keyword + date, `low` = date right after a line count |
| `account_name` / `account_name_raw` | repaired vs original (mojibake such as `MÃ©TODEX` → `MÉTODEX`) |

### Line-count parsing rules (summary)

The full, commented rules live in `importer/line_parser.py`; the examples are
pinned by `importer/tests/test_line_parser.py`.

* A number immediately **before** a type token wins: `3 WLS`, `37 MP`, `6X WLS`,
  `3 xmp`, `3x MP`, `2-MP`, `10WLS`, `1 WLS ET +`, `2 | MP |`, `NAME-3MP`.
* Otherwise a number immediately **after** it: `MP 5 |`, `WLS 16 |`, `WLS x 18`,
  `MP x3`, `MP 50+` (→ 50), `WLS - 10 renewals`, `WLS RNW - 3 lines`.
* Both types: `2 MP + 3 WLS` → MP 2, WLS 3, total 5, type *Both*.
* Type with no number (`WLS`, `-MP`) → type known, count Unknown.
* `WLS - 2 MP` (very common) → count 2, type **MP** (the counted lines); WLS is
  recorded in `types_mentioned`.  Flip `TYPE_FROM_COUNTED_ONLY` in the parser
  if you prefer *Both* for these.
* Ignored: numbers not adjacent to MP/WLS (`3yr`, `2024`, `BF 2024`, `210$`,
  `70G`, `1 TSF`, `15 IOT`, `TSB`), digits glued to longer numbers (years,
  phone and company numbers), numbers followed by another product word
  (`WLS | 2 BCON`), anything above 500.
* Ranges resolve to the upper bound: `9-15 WLS` → 15.

## Data files

| File | Content |
|---|---|
| `data/opportunities.json` | `{meta, opportunities[]}` – loaded by the app |
| `data/closed_lost.sqlite` | `opportunities` (replaced on import), `edits` (yours, kept), `imports` (log) |
| `data/import_report.txt` | last validation report |
| `data/Closed_Lost_Workbench.html` | the single-file app (`make standalone`) |

Back up `data/closed_lost.sqlite` (server mode) or the JSON files you save from the edits menu (single-file mode) to keep your work.

## Tests

```bash
make test         # 134 tests: parser examples, mojibake repair, contract-end hints
```
