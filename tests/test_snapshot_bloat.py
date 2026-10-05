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


@pytest.fixture
def gc_backend(tmp_dir, monkeypatch):
    monkeypatch.setenv("SYNRIX_BACKEND", "sqlite")
    monkeypatch.setenv("SYNRIX_DATA_DIR", tmp_dir)
    from synrix.agent_backend import get_synrix_backend
    backend = get_synrix_backend(backend="sqlite", sqlite_path=f"{tmp_dir}/gc.db")
    yield backend
    backend.close()


def _bulk_rows(backend, names, updated_at):
    # Straight SQL so 20K filler rows take milliseconds instead of a full write path each
    conn = backend.client._get_conn()
    try:
        conn.executemany(
            "INSERT INTO nodes (collection, name, data, created_at, updated_at) VALUES (?, ?, '{}', ?, ?)",
            [(backend.collection, n, updated_at, updated_at) for n in names],
        )
        conn.commit()
    finally:
        conn.close()


def _snapshot_keys(backend, agent_id):
    return {r["key"] for r in backend.query_prefix(f"agents:{agent_id}:snapshots:", limit=100)}


class TestGcSnapshotPruning:
    def _gc(self, backend, keep=10):
        from synrix_runtime.core.gc import GCConfig, GarbageCollector
        config = GCConfig(metrics_days=0, events_days=0, alerts_days=0, audit_days=0, max_snapshots_per_agent=keep)
        return GarbageCollector(backend, config)

    def test_prunes_old_snapshots_hidden_behind_newer_rows(self, gc_backend):
        now = __import__("time").time()
        for i in range(15):
            gc_backend.write(f"agents:agentX:snapshots:auto-{i}", {"value": {"created_at": now - (15 - i) * 60}})
        # Newer rows than every snapshot, more than the old 20,000-row scan window
        _bulk_rows(gc_backend, [f"agents:agentX:memories:m{i}" for i in range(20_100)], now + 1000)

        stats = self._gc(gc_backend).run_gc()

        assert stats["snapshots_pruned"] == 5
        assert _snapshot_keys(gc_backend, "agentX") == {f"agents:agentX:snapshots:auto-{i}" for i in range(5, 15)}

    def test_keeps_newest_per_agent(self, gc_backend):
        now = __import__("time").time()
        for agent in ("a1", "a2"):
            for i in range(4):
                gc_backend.write(f"agents:{agent}:snapshots:s{i}", {"value": {"created_at": now - (4 - i) * 60}})
        assert self._gc(gc_backend, keep=2).run_gc()["snapshots_pruned"] == 4
        assert _snapshot_keys(gc_backend, "a1") == {"agents:a1:snapshots:s2", "agents:a1:snapshots:s3"}


@pytest.fixture
def no_postgres(monkeypatch):
    """Self-hosted SQLite: no DATABASE_URL, and any attempt to reach Postgres is recorded."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from synrix_runtime.api import tenant
    calls = []
    monkeypatch.setattr(tenant.TenantManager, "get_instance", classmethod(lambda cls: calls.append(1) or None))
    monkeypatch.setattr(cs, "_memory_cap_cache", {})
    monkeypatch.setattr(cs, "_tenant_settings", {})
    return calls


class TestPostgresOnlyPathsWithoutDatabaseUrl:
    def test_memory_cap_check_skips_postgres(self, no_postgres):
        cs._enforce_tenant_memory_cap("dev")
        assert no_postgres == []

    def test_platform_usage_skips_postgres_and_allows(self, no_postgres):
        assert cs._check_and_increment_platform_usage("dev") is True
        assert no_postgres == []

    def test_audit_log_is_skipped_quietly(self, no_postgres, capsys):
        from synrix_runtime import audit_v2
        from synrix_runtime.audit_v2 import async_writer
        before = async_writer._queue.qsize()
        assert audit_v2.log("dev", "memory.write", "andrew-context", key="k", value="v") == -1
        assert async_writer._queue.qsize() == before
        assert "failed" not in capsys.readouterr().err
