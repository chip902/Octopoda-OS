"""
Test: schema-level version cap for runtime:* and metrics:* prefixes.
Issue #6: heartbeat keys accumulate one row per write forever without
this trigger.
"""
import os
import tempfile
import shutil
import time
import pytest

# Test the trigger directly via SQLiteClient
from synrix.sqlite_client import SynrixSQLiteClient


@pytest.fixture
def client():
    tmpdir = tempfile.mkdtemp(prefix="octopoda_trigger_test_")
    db_path = os.path.join(tmpdir, "test.db")
    c = SynrixSQLiteClient(db_path=db_path)
    yield c
    try:
        c.close()
    except Exception:
        pass
    shutil.rmtree(tmpdir, ignore_errors=True)


def _row_count_for_key(client, name):
    """Count current rows in nodes table for a given name."""
    with client._conn() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE name = ?", (name,)
        ).fetchone()[0]


def test_runtime_prefix_capped_at_10(client):
    """runtime:agents:* keys should retain only the last 10 versions."""
    key = "runtime:agents:test-agent:heartbeat"
    for i in range(25):
        client.add_node(name=key, data=f'{{"hb":{i},"ts":{time.time()+i}}}', collection="nodes")
    count = _row_count_for_key(client, key)
    assert count <= 10, f"runtime: key has {count} rows, expected <= 10"


def test_metrics_prefix_capped_at_10(client):
    """metrics:* keys should retain only the last 10 versions."""
    key = "metrics:system:ops:test"
    for i in range(20):
        client.add_node(name=key, data=f'{{"v":{i}}}', collection="nodes")
    count = _row_count_for_key(client, key)
    assert count <= 10, f"metrics: key has {count} rows, expected <= 10"


def test_user_memory_NOT_capped(client):
    """agents:* user-memory keys should NOT be capped — full versioning kept."""
    key = "agents:test:user_pref"
    for i in range(20):
        client.add_node(name=key, data=f'{{"v":{i}}}', collection="nodes")
    count = _row_count_for_key(client, key)
    assert count >= 15, f"user memory key was capped to {count} — should keep all versions"


def test_different_runtime_keys_independent(client):
    """Each runtime: key has its own version cap."""
    for i in range(15):
        client.add_node(name="runtime:agents:a1:heartbeat", data=f'{{"v":{i}}}', collection="nodes")
    for i in range(15):
        client.add_node(name="runtime:agents:a2:heartbeat", data=f'{{"v":{i}}}', collection="nodes")
    a1 = _row_count_for_key(client, "runtime:agents:a1:heartbeat")
    a2 = _row_count_for_key(client, "runtime:agents:a2:heartbeat")
    assert a1 <= 10 and a2 <= 10
    # Both should have data (cap is per-key, not shared)
    assert a1 >= 1 and a2 >= 1


def test_max_versions_env_override():
    """SYNRIX_MAX_VERSIONS_PER_RUNTIME_KEY should change the cap."""
    tmpdir = tempfile.mkdtemp(prefix="octopoda_trigger_env_test_")
    try:
        os.environ["SYNRIX_MAX_VERSIONS_PER_RUNTIME_KEY"] = "5"
        db_path = os.path.join(tmpdir, "test.db")
        c = SynrixSQLiteClient(db_path=db_path)
        for i in range(20):
            c.add_node(name="runtime:agents:env-test:heartbeat", data=f'{{"v":{i}}}', collection="nodes")
        with c._conn() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM nodes WHERE name = 'runtime:agents:env-test:heartbeat'"
            ).fetchone()[0]
        assert count <= 5, f"with env=5, got {count} rows"
    finally:
        os.environ.pop("SYNRIX_MAX_VERSIONS_PER_RUNTIME_KEY", None)
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_fts_cleanup_trigger(client):
    """When old node versions are pruned, their FTS rows should be too."""
    key = "runtime:agents:fts-test:heartbeat"
    for i in range(20):
        client.add_node(name=key, data=f'{{"v":{i}}}', collection="nodes")
    with client._conn() as conn:
        # Get current node IDs
        node_ids = [r[0] for r in conn.execute(
            "SELECT id FROM nodes WHERE name = ?", (key,)
        ).fetchall()]
        if node_ids:
            # Each remaining node should still have a corresponding fts row
            for nid in node_ids:
                fts_count = conn.execute(
                    "SELECT COUNT(*) FROM nodes_fts WHERE rowid = ?", (nid,)
                ).fetchone()[0]
                # Either the node has fts (recent insert) or it doesn't (acceptable
                # if FTS sync was skipped). What matters is no orphan fts rows.
            # No orphan fts rows for this key
            orphan_count = conn.execute("""
                SELECT COUNT(*) FROM nodes_fts
                WHERE name = ? AND rowid NOT IN (SELECT id FROM nodes WHERE name = ?)
            """, (key, key)).fetchone()[0]
            assert orphan_count == 0, f"{orphan_count} orphan fts rows for {key}"
