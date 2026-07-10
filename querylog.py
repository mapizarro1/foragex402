import os, json, sqlite3, threading
from datetime import datetime, timezone

DB_PATH = os.environ.get("FORAGEX402_DB", "/var/lib/foragex402/queries.db")
_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS queries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_utc          TEXT NOT NULL,
    query           TEXT NOT NULL,
    caller_key      TEXT,
    client_name     TEXT,
    client_version  TEXT,
    max_price_usdc  REAL,
    per_source_json TEXT,
    merged_count    INTEGER NOT NULL,
    zero_result     INTEGER NOT NULL,
    explicit_miss   INTEGER NOT NULL DEFAULT 0,
    results_json    TEXT,
    latency_ms      INTEGER,
    errors_json     TEXT
);
CREATE INDEX IF NOT EXISTS idx_queries_zero   ON queries(zero_result, ts_utc);
CREATE INDEX IF NOT EXISTS idx_queries_ts     ON queries(ts_utc);
CREATE INDEX IF NOT EXISTS idx_queries_caller ON queries(caller_key, ts_utc);
"""

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as con:
        con.executescript(SCHEMA)

def log_query(query, client_name, client_version, max_price_usdc,
              per_source_counts, merged_count, zero_result, latency_ms,
              errors, explicit_miss=False, caller_key=None, results_served=None):
    row = (
        datetime.now(timezone.utc).isoformat(),
        query, caller_key, client_name, client_version, max_price_usdc,
        json.dumps(per_source_counts), merged_count,
        1 if zero_result else 0, 1 if explicit_miss else 0,
        json.dumps(results_served[:10]) if results_served else None,
        latency_ms, json.dumps(errors) if errors else None,
    )
    with _lock, sqlite3.connect(DB_PATH) as con:
        con.execute(
            "INSERT INTO queries (ts_utc, query, caller_key, client_name,"
            " client_version, max_price_usdc, per_source_json, merged_count,"
            " zero_result, explicit_miss, results_json, latency_ms, errors_json)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", row)
