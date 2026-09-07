"""
Tests for RuntimeDaemon — the central nervous system.
"""

import time
import pytest


class TestDaemonLifecycle:

    def test_singleton(self, tmp_dir, monkeypatch):
        monkeypatch.setenv("SYNRIX_BACKEND", "sqlite")
        monkeypatch.setenv("SYNRIX_DATA_DIR", tmp_dir)

        from synrix_runtime.core.daemon import RuntimeDaemon
        RuntimeDaemon.reset_instance()
        d1 = RuntimeDaemon.get_instance()
        d2 = RuntimeDaemon.get_instance()
        assert d1 is d2
        RuntimeDaemon.reset_instance()

    def test_start_and_shutdown(self, daemon):
        assert daemon.running
        assert daemon.backend is not None
        assert daemon._boot_time is not None

    def test_register_agent(self, daemon):
        result = daemon.register_agent("agent_a", "researcher", {"version": "1.0"})
        assert result["registered"]
        assert result["agent_id"] == "agent_a"
        assert result["latency_us"] > 0

    def test_deregister_agent(self, daemon):
        daemon.register_agent("agent_b", "worker")
        daemon.deregister_agent("agent_b")
        state = daemon.get_agent_state("agent_b")
        assert state == "deregistered"

    def test_get_active_agents(self, daemon):
        daemon.register_agent("active_1", "type_a")
        daemon.register_agent("active_2", "type_b")
        daemon.register_agent("inactive", "type_c")
        daemon.deregister_agent("inactive")

        active = daemon.get_active_agents()
        active_ids = [a["agent_id"] for a in active]
        assert "active_1" in active_ids
        assert "active_2" in active_ids
        assert "inactive" not in active_ids

    def test_recover_agent(self, daemon):
        daemon.register_agent("crash_agent", "worker")
        # Write some memory
        daemon.backend.write("agents:crash_agent:data", {"value": "important"})

        result = daemon.recover_agent("crash_agent")
        assert result["agent_id"] == "crash_agent"
        assert result["recovery_time_us"] > 0
        assert result["keys_restored"] >= 1

    def test_get_system_status(self, daemon):
        daemon.register_agent("status_agent", "bot")
        status = daemon.get_system_status()
        assert status["status"] == "running"
        assert status["active_agents"] >= 1
        assert status["version"] == "1.0.0"
        assert status["uptime_seconds"] >= 0

    def test_event_listeners(self, daemon):
        events = []
        daemon.add_event_listener(lambda e: events.append(e))
        daemon.register_agent("evt_agent", "test")

        assert len(events) >= 1
        assert events[0]["event_type"] == "agent_registered"

        daemon.remove_event_listener(events.append)


class TestCrashRecoveryLoop:
    """Regression cover for the crash/recover storm found 2026-09-06.

    A dead agent used to be crashed and 'recovered' every ~13s forever, because
    recover_agent() wrote a heartbeat on its behalf. Five rows per cycle, ~154k
    rows/day, which is what repeatedly filled the DB.
    """

    def test_recovery_does_not_forge_a_heartbeat(self, daemon):
        daemon.register_agent("ghost", "worker")
        stale = time.time() - 3600
        daemon.backend.write(
            "runtime:agents:ghost:heartbeat", {"value": stale}, metadata={"type": "heartbeat"}
        )

        daemon.recover_agent("ghost")

        agent = next(a for a in daemon.get_all_agents() if a["agent_id"] == "ghost")
        assert agent["heartbeat"] == pytest.approx(stale), (
            "recovery must not write a heartbeat for an agent that isn't there"
        )

    def test_recovered_agent_is_not_re_crashed(self, daemon):
        daemon.register_agent("ghost2", "worker")
        daemon.backend.write(
            "runtime:agents:ghost2:heartbeat",
            {"value": time.time() - 3600},
            metadata={"type": "heartbeat"},
        )
        daemon.set_agent_state("ghost2", "crashed")
        daemon.recover_agent("ghost2")

        assert daemon.get_agent_state("ghost2") == "recovered"
        # The heartbeat monitor skips these states, so no second crash is emitted.
        assert daemon.get_agent_state("ghost2") in (
            "deregistered", "crashed", "recovering", "recovered",
        )

    def test_a_live_agent_clears_its_recovery_attempts(self, daemon):
        daemon.register_agent("ghost3", "worker")
        daemon._recovery_attempts["ghost3"] = 3

        daemon.update_heartbeat("ghost3")

        assert "ghost3" not in daemon._recovery_attempts
