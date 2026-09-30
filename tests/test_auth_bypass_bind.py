"""SYNRIX_AUTH_DISABLED on a non-loopback bind is refused unless the operator opts in explicitly
(self-hosted Docker binds 0.0.0.0 and is reached over a private network)."""
import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import synrix_runtime.api.cloud_server as cs


@pytest.fixture
def public_bind(monkeypatch):
    monkeypatch.setattr(cs, "_config", SimpleNamespace(api_host="0.0.0.0"))


def test_bypass_refused_on_public_bind_by_default(public_bind, monkeypatch):
    monkeypatch.setenv("SYNRIX_AUTH_DISABLED", "1")
    monkeypatch.delenv("SYNRIX_AUTH_DISABLED_ALLOW_NONLOOPBACK", raising=False)
    with pytest.raises(HTTPException) as err:
        asyncio.run(cs.verify_auth(None))
    assert err.value.status_code == 403


def test_bypass_allowed_on_public_bind_with_explicit_opt_in(public_bind, monkeypatch):
    monkeypatch.setenv("SYNRIX_AUTH_DISABLED", "1")
    monkeypatch.setenv("SYNRIX_AUTH_DISABLED_ALLOW_NONLOOPBACK", "1")
    tenant = asyncio.run(cs.verify_auth(None))
    assert tenant["tenant_id"] == "dev"


def test_opt_in_alone_does_not_disable_auth(public_bind, monkeypatch):
    monkeypatch.delenv("SYNRIX_AUTH_DISABLED", raising=False)
    monkeypatch.setenv("SYNRIX_AUTH_DISABLED_ALLOW_NONLOOPBACK", "1")
    with pytest.raises(HTTPException):
        asyncio.run(cs.verify_auth(None))
