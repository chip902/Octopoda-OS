"""Regression tests for the Brain pause deadlock seen on 2026-09-29.

A legit 38-write backlog sync pushed an agent to orange, the v1->v2 wiring
auto-paused it, and it stayed paused forever: the cached loop score never
expired, the pause never expired, and a manual resume lasted one write.

Covers the fixes plus guards on the behaviour that should not change:
  1. cached loop detections expire once the agent is quiet, and the
     auto-pause trips on the live score rather than the cached one
  2. automatic pauses expire; manual and dashboard apply-fix pauses don't
  3. SYNRIX_LOOP_PAUSE_EXEMPT_AGENTS opts ingest agents out of auto-pause
  4. resume and delete wipe the agent's loop history
"""
from __future__ import annotations

import importlib
import pathlib
import re
import time as _real_time
import uuid
from concurrent.futures import Future
from unittest.mock import MagicMock

import pytest

from synrix_runtime.api import runtime as runtime_mod

TTL_ENV_VARS = (
    "SYNRIX_LOOP_CACHE_TTL_SEC",
    "SYNRIX_LOOP_PAUSE_TTL_SEC",
    "SYNRIX_LOOP_PAUSE_EXEMPT_AGENTS",
)
AUTO_REASON = "v1_severity:orange:signals=2:score=37"


class FakeClock:
    """Stands in for the time module: time() is frozen, everything else is real."""

    def __init__(self, start: float):
        self.now = start

    def time(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds

    def __getattr__(self, name):
        return getattr(_real_time, name)


def _brain():
    # test_audit_bugfixes_3_1_12 reimports brain, so always grab the live module,
    # not the one this file saw at import time.
    return importlib.import_module("synrix_runtime.monitoring.brain")


def _forget_agent(agent_id: str) -> None:
    # Loop state is module-level, so scrub anything keyed to this agent.
    suffix = f":{agent_id}"
    for store in (runtime_mod._write_tracker, runtime_mod._repeat_tracker,
                  runtime_mod._loop_status_cache, _brain().LoopBreaker._paused_agents):
        for key in [k for k in store if k.endswith(suffix)]:
            store.pop(key, None)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in TTL_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def clock(monkeypatch):
    fake = FakeClock(_real_time.time())
    monkeypatch.setattr(runtime_mod, "time", fake)
    monkeypatch.setattr(_brain(), "time", fake)
    return fake


@pytest.fixture
def breaker():
    return _brain().LoopBreaker


@pytest.fixture
def agent_id():
    aid = f"deadlock-{uuid.uuid4().hex[:8]}"
    yield aid
    _forget_agent(aid)


@pytest.fixture
def loop_agent(agent_runtime, clock):
    yield agent_runtime
    _forget_agent(agent_runtime.agent_id)


def _burst(agent, writes: int = 12, key: str = "sync:cursor") -> None:
    for i in range(writes):
        agent.remember(key, {"batch": i})


# ---------------------------------------------------------------------------
# 1. Cached loop detections expire once the agent is quiet
# ---------------------------------------------------------------------------

def test_quiet_agent_drops_cached_loop_after_default_ttl(loop_agent, clock):
    _burst(loop_agent)
    assert loop_agent.get_loop_status()["severity"] in ("orange", "red")

    clock.advance(1801)
    status = loop_agent.get_loop_status()

    assert status["score"] == 100
    assert status["severity"] == "green"
    assert loop_agent.get_loop_status()["severity"] == "green"


def test_cache_ttl_comes_from_env(loop_agent, clock, monkeypatch):
    monkeypatch.setenv("SYNRIX_LOOP_CACHE_TTL_SEC", "60")
    _burst(loop_agent)
    assert loop_agent.get_loop_status()["severity"] in ("orange", "red")

    # 301s clears the 5-minute write window but is far below the 1800s default
    clock.advance(301)

    assert loop_agent.get_loop_status()["severity"] == "green"


def test_quiet_agent_keeps_cached_loop_inside_ttl(loop_agent, clock):
    _burst(loop_agent)
    burst_score = loop_agent.get_loop_status()["score"]

    clock.advance(600)
    status = loop_agent.get_loop_status()

    assert status["score"] == burst_score
    assert status["severity"] in ("orange", "red")


def test_active_loop_keeps_worst_cached_score_even_past_ttl(loop_agent, clock):
    _burst(loop_agent, writes=12)
    worst = loop_agent.get_loop_status()["score"]

    clock.advance(2000)
    _burst(loop_agent, writes=6)  # milder, but still an active loop (<80)
    status = loop_agent.get_loop_status()

    assert status["score"] == worst


def test_loop_status_reports_live_score_next_to_cached_one(loop_agent, clock):
    _burst(loop_agent)
    assert loop_agent.get_loop_status()["live_severity"] in ("orange", "red")

    clock.advance(400)  # write window is empty, cached entry still inside its TTL
    status = loop_agent.get_loop_status()

    assert status["severity"] in ("orange", "red")
    assert status["live_score"] == 100
    assert status["live_severity"] == "green"


# ---------------------------------------------------------------------------
# 2. Automatic pauses expire, manual pauses never do
# ---------------------------------------------------------------------------

def test_automatic_pause_expires_after_default_ttl(clock, agent_id, breaker):
    breaker.pause_agent("t1", agent_id, reason=AUTO_REASON)

    clock.advance(1801)

    assert breaker.is_paused("t1", agent_id) is False
    assert f"t1:{agent_id}" not in breaker._paused_agents


def test_automatic_pause_holds_inside_ttl(clock, agent_id, breaker):
    breaker.pause_agent("t1", agent_id, reason=AUTO_REASON)

    clock.advance(1799)

    assert breaker.is_paused("t1", agent_id) is True


def test_pause_ttl_comes_from_env(clock, agent_id, monkeypatch, breaker):
    monkeypatch.setenv("SYNRIX_LOOP_PAUSE_TTL_SEC", "60")
    breaker.pause_agent("t1", agent_id, reason="circuit_breaker:spend=$1/60s>0.5/min")

    clock.advance(61)

    assert breaker.is_paused("t1", agent_id) is False


def test_manual_pause_never_expires(clock, agent_id, breaker):
    breaker.pause_agent("t1", agent_id, reason="manual")

    clock.advance(30 * 24 * 3600)

    assert breaker.is_paused("t1", agent_id) is True


def test_dashboard_apply_fix_pause_never_expires(clock, agent_id, breaker):
    # The dashboard checkbox reads "Pause agent until I fix the code"
    from synrix_runtime.loop_intel_v2.api import _maybe_pause_agent
    assert _maybe_pause_agent("t1", agent_id) == {"paused": True}

    clock.advance(30 * 24 * 3600)

    assert breaker.is_paused("t1", agent_id) is True


def test_automatic_pause_does_not_turn_a_manual_one_into_a_timed_one(clock, agent_id, breaker):
    breaker.pause_agent("t1", agent_id, reason="manual")
    breaker.pause_agent("t1", agent_id, reason=AUTO_REASON)  # e.g. cost breaker firing late

    clock.advance(1801)

    assert breaker.is_paused("t1", agent_id) is True


def test_manual_pause_replaces_an_automatic_one(clock, agent_id, breaker):
    breaker.pause_agent("t1", agent_id, reason=AUTO_REASON)
    breaker.pause_agent("t1", agent_id, reason="manual")

    clock.advance(1801)

    assert breaker.is_paused("t1", agent_id) is True


# ---------------------------------------------------------------------------
# 3. Ingest agents can opt out of automatic pauses
# ---------------------------------------------------------------------------

def test_exempt_agent_is_not_paused_by_v1_severity_trip(agent_id, monkeypatch, breaker):
    from synrix_runtime.loop_intel_v2 import circuit_breaker as cb
    monkeypatch.setenv("SYNRIX_LOOP_PAUSE_EXEMPT_AGENTS", f"other, {agent_id}")
    conn = MagicMock()

    result = cb.trip_on_v1_severity(conn, "t1", agent_id, severity="red", score=10)

    assert result is None
    assert breaker.is_paused("t1", agent_id) is False
    conn.cursor.return_value.execute.assert_not_called()


def test_non_exempt_agent_still_paused_by_v1_severity_trip(agent_id, monkeypatch, breaker):
    from synrix_runtime.loop_intel_v2 import circuit_breaker as cb
    monkeypatch.setenv("SYNRIX_LOOP_PAUSE_EXEMPT_AGENTS", "some-ingest-agent")

    result = cb.trip_on_v1_severity(MagicMock(), "t1", agent_id, severity="red", score=10)

    assert result["paused"] is True
    assert breaker.is_paused("t1", agent_id) is True


def test_cost_breaker_skips_exempt_agent_but_pauses_others(monkeypatch, breaker):
    from synrix_runtime.loop_intel_v2 import circuit_breaker as cb
    ingest, worker = f"ingest-{uuid.uuid4().hex[:8]}", f"worker-{uuid.uuid4().hex[:8]}"
    monkeypatch.setenv("SYNRIX_LOOP_PAUSE_EXEMPT_AGENTS", ingest)
    monkeypatch.setattr(cb, "compute_recent_spend", lambda conn, tid: {ingest: 5.0, worker: 5.0})
    monkeypatch.setattr(cb, "_resolve_threshold", lambda cur, tid, aid: (0.5, None, 1))
    try:
        actions = cb.check_tenant(MagicMock(), "t1")

        assert [a["agent_id"] for a in actions] == [worker]
        assert breaker.is_paused("t1", ingest) is False
        assert breaker.is_paused("t1", worker) is True
    finally:
        _forget_agent(ingest)
        _forget_agent(worker)


def test_manual_pause_still_works_on_exempt_agent(agent_id, monkeypatch, breaker):
    monkeypatch.setenv("SYNRIX_LOOP_PAUSE_EXEMPT_AGENTS", agent_id)

    breaker.pause_agent("t1", agent_id, reason="manual")

    assert breaker.is_paused("t1", agent_id) is True


def test_dashboard_apply_fix_pause_still_works_on_exempt_agent(agent_id, monkeypatch, breaker):
    from synrix_runtime.loop_intel_v2.api import _maybe_pause_agent
    monkeypatch.setenv("SYNRIX_LOOP_PAUSE_EXEMPT_AGENTS", agent_id)

    _maybe_pause_agent("t1", agent_id)

    assert breaker.is_paused("t1", agent_id) is True


def test_exempt_agent_still_reports_loop_status(loop_agent, monkeypatch):
    monkeypatch.setenv("SYNRIX_LOOP_PAUSE_EXEMPT_AGENTS", loop_agent.agent_id)
    _burst(loop_agent)

    status = loop_agent.get_loop_status()

    assert status["severity"] in ("orange", "red")
    assert {s["type"] for s in status["signals"]} >= {"key_overwrite", "velocity_spike"}


# ---------------------------------------------------------------------------
# End to end through POST /remember (the path that deadlocked live)
# ---------------------------------------------------------------------------

class _InlinePool:
    """Runs background work inline so the v1->v2 trip lands before the next request."""

    def submit(self, fn, *args, **kwargs):
        fut = Future()
        try:
            fut.set_result(fn(*args, **kwargs))
        except Exception as exc:
            fut.set_exception(exc)
        return fut


@pytest.fixture
def api(api_client, clock, monkeypatch):
    from synrix_runtime.api import cloud_server
    monkeypatch.setattr(cloud_server, "_bg_work_pool", _InlinePool())
    return api_client


def _post_until_paused(api, agent_id: str, max_writes: int = 20) -> list:
    codes = []
    for i in range(max_writes):
        resp = api.post(f"/v1/agents/{agent_id}/remember",
                        json={"key": "sync:cursor", "value": {"batch": i}})
        codes.append(resp.status_code)
        if resp.status_code == 429:
            assert "paused by Brain kill switch" in resp.json()["detail"]
            break
    return codes


def test_api_auto_paused_agent_can_write_again_after_ttl(api, clock, agent_id):
    codes = _post_until_paused(api, agent_id)
    assert codes[-1] == 429, f"burst never tripped the auto-pause: {codes}"

    clock.advance(1801)
    first = api.post(f"/v1/agents/{agent_id}/remember", json={"key": "k1", "value": 1})
    second = api.post(f"/v1/agents/{agent_id}/remember", json={"key": "k2", "value": 2})

    assert first.status_code == 200
    assert second.status_code == 200, "stale cached loop re-paused the agent"


def _fresh_writes(api, agent_id: str, count: int) -> list:
    # Distinct keys, so on their own these never look like a loop.
    return [api.post(f"/v1/agents/{agent_id}/remember",
                     json={"key": f"after:{i}", "value": i}).status_code
            for i in range(count)]


def test_api_status_poll_after_pause_does_not_extend_lockout(api, clock, agent_id):
    codes = _post_until_paused(api, agent_id)
    assert codes[-1] == 429, f"burst never tripped the auto-pause: {codes}"

    # A dashboard or MCP poll while paused rewrites the cached entry's time
    clock.advance(30)
    polled = api.get(f"/v1/agents/{agent_id}/loops/status").json()
    assert polled["severity"] in ("orange", "red")

    clock.advance(1771)  # pause is 1801s old, cached entry only 1771s

    assert _fresh_writes(api, agent_id, 2) == [200, 200]


def test_api_exempt_agent_is_never_auto_paused(api, agent_id, monkeypatch):
    monkeypatch.setenv("SYNRIX_LOOP_PAUSE_EXEMPT_AGENTS", agent_id)

    codes = _post_until_paused(api, agent_id)
    status = api.get(f"/v1/agents/{agent_id}/loops/status").json()

    assert 429 not in codes
    assert status["severity"] in ("orange", "red")


# ---------------------------------------------------------------------------
# Resume and purge start the agent's loop tracking over
# ---------------------------------------------------------------------------

def test_api_resume_right_after_burst_lets_writes_through(api, agent_id):
    codes = _post_until_paused(api, agent_id)
    assert codes[-1] == 429, f"burst never tripped the auto-pause: {codes}"

    assert api.post(f"/v1/brain/resume/{agent_id}").status_code == 200

    assert _fresh_writes(api, agent_id, 3) == [200, 200, 200]
    assert api.get(f"/v1/agents/{agent_id}/loops/status").json()["severity"] == "green"


def test_api_resumed_agent_that_loops_again_is_paused_again(api, agent_id):
    assert _post_until_paused(api, agent_id)[-1] == 429
    api.post(f"/v1/brain/resume/{agent_id}")

    codes = _post_until_paused(api, agent_id)

    assert codes[-1] == 429, f"a fresh burst after resume should still trip: {codes}"


def test_api_deleted_agent_comes_back_with_clean_loop_state(api, agent_id):
    assert _post_until_paused(api, agent_id)[-1] == 429

    # Soft delete runs the same release step as ?purge=true, which needs Postgres
    assert api.delete(f"/v1/agents/{agent_id}").status_code == 200

    assert _fresh_writes(api, agent_id, 3) == [200, 200, 200]


# ---------------------------------------------------------------------------
# Deployment: the settings have to reach the container
# ---------------------------------------------------------------------------

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_compose_passes_loop_settings_through_to_the_api_container():
    # compose only uses .env for ${} substitution, so each var has to be listed under environment:
    documented = re.findall(r"(?m)^(SYNRIX_LOOP_\w+)=", (REPO_ROOT / ".env.example").read_text())
    compose = (REPO_ROOT / "docker-compose.yml").read_text()

    missing = [name for name in documented if f"{name}=${{{name}" not in compose]

    assert len(documented) == 3
    assert missing == []
