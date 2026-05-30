"""Regression: agent enumeration in self-hosted / auth-disabled mode.

In self-hosted mode (SYNRIX_AUTH_DISABLED=1) agent data lives in the daemon
backend, not a per-tenant TenantManager backend. `GET /v1/agents`, `/v1/status`,
etc. previously read only the (empty) per-tenant backend and reported zero agents
even though the daemon backend held registered agents and their memories — while
search/recall worked, because those paths use the daemon runtime directly.

These assert the enumeration endpoints agree with the data the daemon actually
holds. See fix/list-agents-selfhosted-daemon-backend.
"""


class TestListAgentsSelfHosted:
    def test_registered_agent_appears_in_list(self, api_client):
        api_client.post("/v1/agents", json={"agent_id": "alpha"})
        resp = api_client.get("/v1/agents")
        assert resp.status_code == 200
        data = resp.json()
        ids = {a.get("agent_id") for a in data.get("agents", [])}
        assert "alpha" in ids, f"registered agent missing from list: {data}"
        assert data["total"] >= 1

    def test_agent_with_memory_appears_in_list(self, api_client):
        api_client.post("/v1/agents", json={"agent_id": "beta"})
        api_client.post("/v1/agents/beta/remember", json={"key": "k", "value": "v"})
        resp = api_client.get("/v1/agents")
        ids = {a.get("agent_id") for a in resp.json().get("agents", [])}
        assert "beta" in ids

    def test_status_reports_registered_agents(self, api_client):
        api_client.post("/v1/agents", json={"agent_id": "gamma"})
        resp = api_client.get("/v1/status")
        assert resp.status_code == 200
        assert resp.json()["total_agents"] >= 1
