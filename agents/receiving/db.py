"""SQLite storage for the Receiving v2 agent: one process, one file, no broker.

Tables (plan section 3, plus `records`):

- `manifest_lines`  what was ordered (org-scoped; the tenancy boundary)
- `receivings`      one row per scan session (UI lifecycle state, mutable internally)
- `photos`          captured media, hashed, per attempt
- `records`         APPEND-ONLY contract Evidence Records (JSON blobs, immutable)
- `events`          append-only handoff feed (RECEIVING_FINAL / RECEIVING_OVERRIDDEN)
- `damage_cache`    sha256(photos + prompt_version) -> VLM result (real model output only)

Evidence immutability rule: nothing in `records` is ever updated in place except
appending an agent-level `overrides[]` entry, which sits *outside* the content hash
(contract section 10 / EVIDENCE-CONTRACT "append-only").
"""
from __future__ import annotations

import csv
import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS manifest_lines (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  org_id TEXT NOT NULL,
  unit_id TEXT,
  po_id TEXT NOT NULL,
  line_no INTEGER NOT NULL,
  gtin TEXT NOT NULL DEFAULT '',
  sku TEXT NOT NULL DEFAULT '',
  asin TEXT NOT NULL DEFAULT '',
  description TEXT NOT NULL DEFAULT '',
  qty_expected INTEGER,
  lot TEXT NOT NULL DEFAULT '',
  expiry TEXT NOT NULL DEFAULT '',
  supplier TEXT NOT NULL DEFAULT '',
  UNIQUE (org_id, po_id, line_no)
);
CREATE INDEX IF NOT EXISTS idx_manifest_subject ON manifest_lines (org_id, unit_id);

CREATE TABLE IF NOT EXISTS receivings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  rcv_id TEXT NOT NULL UNIQUE,
  scan_key TEXT NOT NULL UNIQUE,
  workflow_id TEXT NOT NULL,
  org_id TEXT NOT NULL,
  subject_id TEXT NOT NULL,
  manifest_line_id INTEGER REFERENCES manifest_lines (id),
  qty_received INTEGER,
  lot_entered TEXT NOT NULL DEFAULT '',
  expiry_entered TEXT NOT NULL DEFAULT '',
  attempt INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL,
  verdict TEXT,
  reasons TEXT NOT NULL DEFAULT '[]',
  facts TEXT NOT NULL DEFAULT '{}',
  rules_version TEXT NOT NULL,
  operator TEXT,
  effective_record_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_receivings_subject ON receivings (org_id, subject_id);
CREATE INDEX IF NOT EXISTS idx_receivings_status ON receivings (status);

CREATE TABLE IF NOT EXISTS photos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  receiving_id INTEGER NOT NULL REFERENCES receivings (id),
  role TEXT NOT NULL,
  attempt INTEGER NOT NULL DEFAULT 0,
  sha256 TEXT NOT NULL,
  path TEXT NOT NULL,
  quality TEXT NOT NULL DEFAULT '{}',
  barcode TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_photos_receiving ON photos (receiving_id, attempt);

CREATE TABLE IF NOT EXISTS records (
  record_id TEXT PRIMARY KEY,
  rcv_id TEXT NOT NULL,
  attempt INTEGER NOT NULL,
  record_json TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_records_rcv ON records (rcv_id);

CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  type TEXT NOT NULL,
  receiving_id TEXT NOT NULL,
  record_id TEXT,
  payload TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS damage_cache (
  cache_key TEXT PRIMARY KEY,
  result TEXT NOT NULL,
  model TEXT,
  created_at TEXT NOT NULL
);
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@contextmanager
def connect():
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        _seed_manifest(conn)


def _seed_manifest(conn: sqlite3.Connection) -> None:
    """Load the sample CSV once so every demo subject resolves (and tenancy works)."""
    count = conn.execute("SELECT COUNT(*) AS n FROM manifest_lines").fetchone()["n"]
    if count or not config.MANIFEST_SEED.exists():
        return
    import_manifest_rows(conn, _sample_manifest_rows(config.MANIFEST_SEED), org_default=None)


def _sample_manifest_rows(path: Path) -> list[dict]:
    rows = []
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows.append({
                "org_id": r["org_id"], "unit_id": r["unit_id"], "po_id": r["po_number"],
                "line_no": int(r["po_line"]), "gtin": "", "sku": r["sku"], "asin": r["asin"],
                "description": r["product_title"], "qty_expected": int(r["qty_ordered"]),
                "lot": "", "expiry": "", "supplier": r["supplier"],
            })
    return rows


def import_manifest_rows(conn: sqlite3.Connection, rows: list[dict], org_default: str | None) -> int:
    """Upsert manifest lines keyed by (org_id, po_id, line_no). Returns rows written."""
    written = 0
    for row in rows:
        org = (row.get("org_id") or org_default or "").strip()
        if not org:
            raise ValueError("manifest row has no org_id and no default org was given")
        conn.execute(
            """INSERT INTO manifest_lines
               (org_id, unit_id, po_id, line_no, gtin, sku, asin, description,
                qty_expected, lot, expiry, supplier)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT (org_id, po_id, line_no) DO UPDATE SET
                 unit_id=excluded.unit_id, gtin=excluded.gtin, sku=excluded.sku,
                 asin=excluded.asin, description=excluded.description,
                 qty_expected=excluded.qty_expected, lot=excluded.lot,
                 expiry=excluded.expiry, supplier=excluded.supplier""",
            (org, (row.get("unit_id") or "").strip() or None,
             (row.get("po_id") or "").strip(), int(row.get("line_no") or 0),
             (row.get("gtin") or "").strip(), (row.get("sku") or "").strip(),
             (row.get("asin") or "").strip(), (row.get("description") or "").strip(),
             int(row["qty_expected"]) if str(row.get("qty_expected") or "").strip() else None,
             (row.get("lot") or "").strip(), (row.get("expiry") or "").strip(),
             (row.get("supplier") or "").strip()),
        )
        written += 1
    return written


def parse_manifest_csv(text: str, org_default: str | None) -> list[dict]:
    reader = csv.DictReader(text.splitlines())
    if not reader.fieldnames or "po_id" not in reader.fieldnames:
        raise ValueError("manifest CSV needs at least: po_id,line_no")
    return [dict(r) for r in reader]


# --- lookups (tenancy: every lookup is org-scoped; miss -> LookupError upstream) -------------

def find_manifest_line(org_id: str, unit_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM manifest_lines WHERE org_id=? AND unit_id=? ORDER BY id LIMIT 1",
            (org_id, unit_id),
        ).fetchone()
        return dict(row) if row else None


def list_manifest(org_id: str | None = None) -> list[dict]:
    with connect() as conn:
        if org_id:
            rows = conn.execute("SELECT * FROM manifest_lines WHERE org_id=? ORDER BY po_id, line_no", (org_id,))
        else:
            rows = conn.execute("SELECT * FROM manifest_lines ORDER BY org_id, po_id, line_no")
        return [dict(r) for r in rows]


def get_manifest_line(org_id: str, line_id: int) -> dict | None:
    """Org-scoped fetch by primary key: a line id from another tenant is a miss."""
    with connect() as conn:
        row = conn.execute("SELECT * FROM manifest_lines WHERE id=? AND org_id=?",
                           (line_id, org_id)).fetchone()
        return dict(row) if row else None


def org_gtins(org_id: str) -> set[str]:
    with connect() as conn:
        rows = conn.execute("SELECT gtin FROM manifest_lines WHERE org_id=? AND gtin!=''", (org_id,))
        return {r["gtin"] for r in rows}


def records_for(rcv_id: str) -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT record_id, record_json, created_at FROM records "
                            "WHERE rcv_id=? ORDER BY created_at, record_id", (rcv_id,))
        return [{**json.loads(r["record_json"]), "_stored_at": r["created_at"]} for r in rows]


def barcode_known_elsewhere(org_id: str, gtin: str, exclude_line_id: int | None) -> dict | None:
    """A decoded GTIN that is on a *different* manifest line for this org (WRONG_SKU)."""
    if not gtin:
        return None
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM manifest_lines WHERE org_id=? AND gtin=? AND id!=? ORDER BY id LIMIT 1",
            (org_id, gtin, exclude_line_id or -1),
        ).fetchone()
        return dict(row) if row else None


# --- rcv id sequencing ------------------------------------------------------------------------

def next_rcv_id(conn: sqlite3.Connection) -> str:
    seq = max(config.SEED_RCV_SEQ, 0)
    for (value,) in conn.execute("SELECT rcv_id FROM receivings"):
        m = re.fullmatch(r"RCV-(\d+)", value or "")
        if m:
            seq = max(seq, int(m.group(1)))
    return f"RCV-{seq + 1:04d}"


# --- receivings -------------------------------------------------------------------------------

def create_receiving(*, rcv_id: str, scan_key: str, workflow_id: str, org_id: str, subject_id: str,
                     manifest_line_id: int | None, qty_received: int | None, lot_entered: str,
                     expiry_entered: str, status: str, operator: str | None) -> int:
    now = utcnow()
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO receivings
               (rcv_id, scan_key, workflow_id, org_id, subject_id, manifest_line_id,
                qty_received, lot_entered, expiry_entered, attempt, status, rules_version,
                operator, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,0,?,?,?,?,?)""",
            (rcv_id, scan_key, workflow_id, org_id, subject_id, manifest_line_id,
             qty_received, lot_entered, expiry_entered, status, config.RULES_VERSION,
             operator, now, now),
        )
        return int(cur.lastrowid)


def get_receiving_by_scan_key(scan_key: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM receivings WHERE scan_key=?", (scan_key,)).fetchone()
        return dict(row) if row else None


def get_receiving(rcv_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM receivings WHERE rcv_id=?", (rcv_id,)).fetchone()
        return dict(row) if row else None


def list_receivings(status: str | None = None, verdict: str | None = None,
                    org_id: str | None = None, source: str | None = None) -> list[dict]:
    """UI/review listing. `verdict` and `status` use the plan's 4-state vocabulary
    (ACCEPT / QUARANTINE / REJECT / ESCALATE), which is what the receivings row stores.
    `source` = "ui" restricts to physical scans (the review queue); orchestrator-driven
    runs without captures also land in final_open but are not operator work."""
    sql, params, clauses = "SELECT * FROM receivings", [], []
    if status:
        clauses.append("status=?")
        params.append(status)
    if verdict:
        clauses.append("verdict=?")
        params.append(verdict)
    if org_id:
        clauses.append("org_id=?")
        params.append(org_id)
    if source:
        clauses.append("rcv_id IN (SELECT rcv_id FROM records WHERE record_json LIKE ?)")
        params.append(f'%"source": "{source}"%')
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY id"
    with connect() as conn:
        return [dict(r) for r in conn.execute(sql, params)]


def update_receiving(rcv_id: str, **fields) -> None:
    if not fields:
        return
    fields["updated_at"] = utcnow()
    cols = ", ".join(f"{k}=?" for k in fields)
    with connect() as conn:
        conn.execute(f"UPDATE receivings SET {cols} WHERE rcv_id=?",
                     (*fields.values(), rcv_id))


# --- photos -----------------------------------------------------------------------------------

def add_photo(receiving_id: int, *, role: str, attempt: int, sha256: str, path: str,
              quality: dict, barcode: dict) -> None:
    with connect() as conn:
        conn.execute(
            """INSERT INTO photos (receiving_id, role, attempt, sha256, path, quality, barcode, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (receiving_id, role, attempt, sha256, path, json.dumps(quality), json.dumps(barcode), utcnow()),
        )


def photos_for(receiving_id: int, attempt: int | None = None) -> list[dict]:
    with connect() as conn:
        if attempt is None:
            rows = conn.execute("SELECT * FROM photos WHERE receiving_id=? ORDER BY id", (receiving_id,))
        else:
            rows = conn.execute("SELECT * FROM photos WHERE receiving_id=? AND attempt=? ORDER BY id",
                                (receiving_id, attempt))
        out = []
        for r in rows:
            d = dict(r)
            d["quality"] = json.loads(d["quality"])
            d["barcode"] = json.loads(d["barcode"])
            out.append(d)
        return out


# --- records (append-only evidence) ------------------------------------------------------------

def save_record(record: dict) -> bool:
    """Store a sealed Evidence Record. Returns False if it already existed (idempotent replay)."""
    with connect() as conn:
        cur = conn.execute(
            """INSERT OR IGNORE INTO records
               (record_id, rcv_id, attempt, record_json, content_hash, created_at)
               VALUES (?,?,?,?,?,?)""",
            (record["record_id"], record["subject"]["refs"].get("rcv_id") or "",
             int(record.get("payload", {}).get("attempt", 0)),
             json.dumps(record, sort_keys=True), record["content_hash"], utcnow()),
        )
        return cur.rowcount == 1


def get_record(record_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT record_json FROM records WHERE record_id=?", (record_id,)).fetchone()
        return json.loads(row["record_json"]) if row else None


def append_override(record_id: str, override: dict) -> dict | None:
    """Append an agent-level override to a stored record. Never rewrites checks/decision.

    Overrides sit outside the content hash, so `content_hash` is preserved verbatim.
    """
    with connect() as conn:
        row = conn.execute("SELECT record_json FROM records WHERE record_id=?", (record_id,)).fetchone()
        if not row:
            return None
        record = json.loads(row["record_json"])
        record["overrides"] = [*record.get("overrides", []), override]
        conn.execute("UPDATE records SET record_json=? WHERE record_id=?",
                     (json.dumps(record, sort_keys=True), record_id))
        return record


# --- events -----------------------------------------------------------------------------------

def append_event(type_: str, receiving_id: str, record_id: str | None, payload: dict) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO events (type, receiving_id, record_id, payload, created_at) VALUES (?,?,?,?,?)",
            (type_, receiving_id, record_id, json.dumps(payload, sort_keys=True), utcnow()),
        )
        return int(cur.lastrowid)


def list_events(since: int = 0) -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM events WHERE id>? ORDER BY id", (since,))
        return [{"event_id": r["id"], "type": r["type"], "receiving_id": r["receiving_id"],
                 "record_id": r["record_id"], "payload": json.loads(r["payload"]),
                 "created_at": r["created_at"]} for r in rows]


# --- damage cache ------------------------------------------------------------------------------

def cache_get(cache_key: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT result FROM damage_cache WHERE cache_key=?", (cache_key,)).fetchone()
        return json.loads(row["result"]) if row else None


def cache_put(cache_key: str, result: dict, model: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO damage_cache (cache_key, result, model, created_at) VALUES (?,?,?,?)",
            (cache_key, json.dumps(result, sort_keys=True), model, utcnow()),
        )
