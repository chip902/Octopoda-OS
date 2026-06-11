#!/usr/bin/env python3
"""Octopoda telemetry cleanup (Path A — widened scope, hourly cadence).

Deletes Octopoda's internal telemetry rows older than RETAIN_HOURS:
  - runtime:*  (heartbeats, baselines, anomaly/recovery events)
  - metrics:*  (system ops counters)
  - alerts:*   (anomaly_alert records — frequently misfires from stale baseline)

NEVER touches:
  - agents:*   (THE actual user memory — Plaud transcripts, decisions, people, prefs)
  - any other prefix not in the explicit allowlist

Runs INSIDE the octopoda-os-api-1 container via `docker exec` (called by
run_cleanup.sh, which stops the API first for exclusive DB access).

Prints a single JSON line to stdout for the wrapper to parse + log + alert.
"""
import json
import os
import sqlite3
import sys
import time

DB = "/data/synrix.db"
RETAIN_HOURS = 2
SIZE_WARN_MB = 400
SIZE_CRIT_MB = 600

# Prefixes that are pure Octopoda telemetry — safe to delete past retention.
TELEMETRY_PREFIXES = ("runtime:", "metrics:", "alerts:")


def main() -> int:
    if not os.path.exists(DB):
        print(json.dumps({"status": "error", "msg": f"DB not found at {DB}"}))
        return 1

    start = time.time()
    try:
        con = sqlite3.connect(DB, timeout=10.0)
        cur = con.cursor()
        cutoff_sql = f"strftime('%s','now','-{RETAIN_HOURS} hours')"

        deleted_by_prefix = {}
        for prefix in TELEMETRY_PREFIXES:
            # AND name NOT LIKE 'agents:%' is structurally redundant given the
            # LIKE clause, but kept as belt-and-suspenders defense against any
            # future telemetry key drift into agents:* namespace.
            cur.execute(
                f"DELETE FROM nodes "
                f"WHERE name LIKE '{prefix}%' "
                f"AND name NOT LIKE 'agents:%' "
                f"AND created_at < {cutoff_sql}"
            )
            deleted_by_prefix[prefix.rstrip(":")] = cur.rowcount

        deleted = sum(deleted_by_prefix.values())
        con.commit()

        total_rows = cur.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        agents_rows = cur.execute(
            "SELECT COUNT(*) FROM nodes WHERE name LIKE 'agents:%'"
        ).fetchone()[0]
        telemetry_remaining = cur.execute(
            "SELECT COUNT(*) FROM nodes WHERE "
            "name LIKE 'runtime:%' OR name LIKE 'metrics:%' OR name LIKE 'alerts:%'"
        ).fetchone()[0]
        cur.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        con.close()
    except sqlite3.Error as e:
        print(json.dumps({"status": "error", "msg": str(e)}))
        return 1

    size_mb = os.path.getsize(DB) / 1024 / 1024
    status = "ok"
    if size_mb > SIZE_CRIT_MB:
        status = "crit"
    elif size_mb > SIZE_WARN_MB:
        status = "warn"

    print(json.dumps({
        "status": status,
        "deleted": deleted,
        "deleted_by_prefix": deleted_by_prefix,
        "total_rows": total_rows,
        "agents_rows_preserved": agents_rows,
        "telemetry_remaining": telemetry_remaining,
        "db_size_mb": round(size_mb, 1),
        "elapsed_s": round(time.time() - start, 1),
        "retention_hours": RETAIN_HOURS,
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
