#!/bin/bash
# One-time full VACUUM. auto_vacuum was set to INCREMENTAL on an already-created
# DB, so no ptrmap pages exist and incremental_vacuum is a no-op until we rebuild.
set -uo pipefail
export PATH="$PATH:/usr/local/bin:/opt/homebrew/bin"
C=octopoda-os-api-1
LOG="$HOME/Library/Logs/octopoda-cleanup.log"
say() { echo "$(date +%Y-%m-%dT%H:%M:%S) $*" | tee -a "$LOG"; }

say "[INFO] vacuum_once: stopping $C"
docker stop --timeout 15 "$C" >/dev/null 2>&1 || { say "[ERROR] stop failed"; exit 1; }

RESULT=$(docker run --rm -i --entrypoint python3 -v octopoda-os_synrix-data:/data octopoda-os-api - <<'PY' 2>&1
import sqlite3, os, time, json
DB = "/data/synrix.db"
before = os.path.getsize(DB)
con = sqlite3.connect(DB, timeout=300, isolation_level=None)
ok = con.execute("PRAGMA integrity_check").fetchone()[0]
if ok != "ok":
    print(json.dumps({"status": "abort", "integrity": ok})); raise SystemExit(1)
a_before = con.execute("SELECT COUNT(*) FROM nodes WHERE name LIKE 'agents:%'").fetchone()[0]
t = time.time()
con.execute("VACUUM")
con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
a_after = con.execute("SELECT COUNT(*) FROM nodes WHERE name LIKE 'agents:%'").fetchone()[0]
fl = con.execute("PRAGMA freelist_count").fetchone()[0]
con.close()
after = os.path.getsize(DB)
print(json.dumps({"status":"ok","integrity":ok,
 "before_MiB":round(before/1048576,1),"after_MiB":round(after/1048576,1),
 "reclaimed_MiB":round((before-after)/1048576,1),"freelist_after":fl,
 "agents_rows_before":a_before,"agents_rows_after":a_after,
 "elapsed_s":round(time.time()-t,1)}))
PY
)
RC=$?
say "[INFO] vacuum_once RC=$RC: $RESULT"

docker start "$C" >/dev/null 2>&1 || { say "[ERROR] start failed"; exit 2; }
for i in $(seq 1 40); do
  CODE=$(curl -s --max-time 5 -o /dev/null -w '%{http_code}' http://localhost:8443/v1/agents || echo 000)
  [ "$CODE" = "200" ] && break
  sleep 3
done
say "[INFO] API after restart: HTTP $CODE"
[ "$CODE" = "200" ] || exit 2
exit "$RC"
