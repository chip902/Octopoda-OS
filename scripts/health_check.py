#!/usr/bin/env python3
"""Octopoda + Mac Mini health check.

Runs on the HOST (not in container). Probes API, DB size, GC duration, system
load, and FRIDAY launchd. Prints one JSON line to stdout.

Exit code: 0=ok, 1=warn, 2=crit/error.
"""
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

CONTAINER = "octopoda-os-api-1"
# Liveness probe MUST be the cheap /health endpoint. /v1/agents aggregates
# per-agent stats over the (~586MB) SQLite DB and spikes to 2-10s on cold/
# contended hits, which tripped WARN_API_S/CRIT_API_S and paged false crits
# while the service was healthy. DB bloat is covered separately by check_db_size.
API_URL = "http://localhost:8443/health"

# Baseline after the 2026-06-11 reclaim is ~258MB (real data + snapshot FTS),
# down from a 585MB telemetry death-spiral. Thresholds sit above baseline with
# headroom to catch a regression toward unbounded growth (was 800/1500).
WARN_DB_MB = 400
CRIT_DB_MB = 600
WARN_GC_S = 30
CRIT_GC_S = 60
WARN_LOAD = 8.0
CRIT_LOAD = 15.0
WARN_API_S = 5.0
CRIT_API_S = 10.0


def run(cmd, timeout=20):
    """Subprocess wrapper that never raises. Returns CompletedProcess-like obj."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        class R:
            returncode = 124
            stdout = ""
            stderr = "timeout"
        return R()
    except Exception as e:
        class R:
            returncode = 125
            stdout = ""
            stderr = f"exec error: {e}"
        return R()


def check_api():
    try:
        t = time.time()
        with urllib.request.urlopen(API_URL, timeout=10) as r:
            r.read(64)
        latency = time.time() - t
        if latency > CRIT_API_S:
            return ("crit", round(latency, 2), f"API slow: {latency:.1f}s")
        if latency > WARN_API_S:
            return ("warn", round(latency, 2), f"API slow: {latency:.1f}s")
        return ("ok", round(latency, 2), "")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return ("crit", -1, f"API unreachable: {e}")
    except Exception as e:
        return ("crit", -1, f"API error: {e}")


def check_db_size():
    res = run(["docker", "exec", CONTAINER, "stat", "-c", "%s", "/data/synrix.db"], timeout=15)
    if res.returncode == 124:
        return ("warn", -1, "docker exec timeout (Mini under load)")
    if res.returncode != 0:
        return ("crit", -1, f"stat failed: {res.stderr.strip()[:120]}")
    try:
        size_mb = int(res.stdout.strip()) / 1024 / 1024
    except ValueError:
        return ("crit", -1, "couldn't parse size")
    if size_mb > CRIT_DB_MB:
        return ("crit", round(size_mb, 0), f"DB {size_mb:.0f}MB")
    if size_mb > WARN_DB_MB:
        return ("warn", round(size_mb, 0), f"DB {size_mb:.0f}MB")
    return ("ok", round(size_mb, 0), "")


def check_gc_duration():
    res = run(["docker", "logs", "--tail", "300", CONTAINER], timeout=15)
    if res.returncode == 124:
        return ("warn", -1, "docker logs timeout")
    if res.returncode != 0:
        return ("crit", -1, "logs unreadable")
    matches = re.findall(r"GC complete:.*?pruned in ([\d.]+)ms", res.stdout + res.stderr)
    if not matches:
        return ("ok", -1, "no GC seen")
    last_s = float(matches[-1]) / 1000.0
    if last_s > CRIT_GC_S:
        return ("crit", round(last_s, 1), f"last GC {last_s:.1f}s")
    if last_s > WARN_GC_S:
        return ("warn", round(last_s, 1), f"last GC {last_s:.1f}s")
    return ("ok", round(last_s, 1), "")


def check_load():
    res = run(["uptime"])
    m = re.search(r"load averages?: ([\d.]+)", res.stdout)
    if not m:
        return ("ok", -1, "no parse")
    load = float(m.group(1))
    if load > CRIT_LOAD:
        return ("crit", round(load, 1), f"load {load:.1f}")
    if load > WARN_LOAD:
        return ("warn", round(load, 1), f"load {load:.1f}")
    return ("ok", round(load, 1), "")


def check_friday():
    res = run(["launchctl", "list"])
    if "com.friday.remote" not in res.stdout:
        return ("crit", -1, "launchd job missing")
    res = run(["pgrep", "-f", "friday_remote.py"])
    if res.returncode != 0:
        return ("crit", -1, "process not running")
    return ("ok", -1, "")


def main() -> int:
    # Wrap each check so a single one blowing up doesn't kill the whole report
    def safe(fn, label):
        try:
            return fn()
        except Exception as e:
            return ("warn", -1, f"{label} probe error: {e}")
    checks = {
        "api": safe(check_api, "api"),
        "db_size_mb": safe(check_db_size, "db_size"),
        "last_gc_s": safe(check_gc_duration, "gc"),
        "load_1m": safe(check_load, "load"),
        "friday": safe(check_friday, "friday"),
    }
    statuses = [c[0] for c in checks.values()]
    overall = "crit" if "crit" in statuses else "warn" if "warn" in statuses else "ok"
    print(json.dumps({
        "overall": overall,
        "checks": {k: {"status": v[0], "value": v[1], "msg": v[2]} for k, v in checks.items()},
    }))
    return 2 if overall == "crit" else 1 if overall == "warn" else 0


if __name__ == "__main__":
    sys.exit(main())
