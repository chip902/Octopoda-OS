"""Regression tests for the snapshot bloat fixes (2026-10-05): auto-snapshot frequency and
exemptions, FTS skipping snapshot keys, GC snapshot pruning, Postgres-only paths without
DATABASE_URL, and the healthcheck's GC detection."""
from __future__ import annotations

import pytest

from synrix_runtime.api import cloud_server as cs


@pytest.fixture
def snapshot_config(monkeypatch):
    """Reset the auto-snapshot counter and let each test set frequency + exemptions."""
    monkeypatch.setattr(cs, "_auto_checkpoint_counter", {})

    def configure(every: int, exempt: set[str] = frozenset()):
        monkeypatch.setattr(cs, "_auto_snapshot_every", every)
        monkeypatch.setattr(cs, "_auto_snapshot_exempt", set(exempt))

    return configure


class TestAutoSnapshotDecision:
    def test_snapshots_on_every_nth_write(self, snapshot_config):
        snapshot_config(every=3)
        decisions = [cs._should_auto_snapshot("dev", "marvin") for _ in range(6)]
        assert decisions == [False, False, True, False, False, True]

    def test_exempt_agent_never_snapshots(self, snapshot_config):
        snapshot_config(every=1, exempt={"andrew-context"})
        assert not any(cs._should_auto_snapshot("dev", "andrew-context") for _ in range(5))

    def test_exempt_list_leaves_other_agents_alone(self, snapshot_config):
        snapshot_config(every=1, exempt={"andrew-context"})
        assert cs._should_auto_snapshot("dev", "marvin")

    def test_zero_turns_auto_snapshots_off(self, snapshot_config):
        snapshot_config(every=0)
        assert not any(cs._should_auto_snapshot("dev", "marvin") for _ in range(5))

    def test_counters_are_per_agent(self, snapshot_config):
        snapshot_config(every=2)
        cs._should_auto_snapshot("dev", "marvin")
        assert not cs._should_auto_snapshot("dev", "friday")
        assert cs._should_auto_snapshot("dev", "marvin")


def _fts_rows(client, name: str) -> int:
    with client._conn() as conn:
        return conn.execute(
            "SELECT count(*) FROM nodes_fts WHERE rowid IN (SELECT id FROM nodes WHERE name = ?)", (name,)
        ).fetchone()[0]


class TestSnapshotKeysSkipFts:
    def test_new_snapshot_key_is_not_indexed(self, sqlite_client):
        sqlite_client.add_node("agents:andrew-context:snapshots:auto-1", data='{"blob": "needle"}')
        assert _fts_rows(sqlite_client, "agents:andrew-context:snapshots:auto-1") == 0

    def test_rewritten_snapshot_key_is_not_indexed(self, sqlite_client):
        sqlite_client.add_node("agents:marvin:snapshots:manual", data='{"v": 1}')
        sqlite_client.add_node("agents:marvin:snapshots:manual", data='{"v": 2}')
        assert _fts_rows(sqlite_client, "agents:marvin:snapshots:manual") == 0

    def test_memory_key_is_still_indexed(self, sqlite_client):
        sqlite_client.add_node("agents:marvin:memories:note", data='{"value": "needle"}')
        assert _fts_rows(sqlite_client, "agents:marvin:memories:note") == 1
