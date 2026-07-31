"""Anthropic HTTP transport factory: trust_env contract and factory wiring."""

import inspect

import httpx
import pytest

import config
from anthropic_http import create_anthropic_client
import claude_service
from strategy import replacement_service


# --- config default contract -------------------------------------------------


def test_default_true_in_development():
    assert config.parse_anthropic_trust_env(None, "development") is True


def test_default_false_in_production():
    assert config.parse_anthropic_trust_env(None, "production") is False


@pytest.mark.parametrize("raw", ["true", "TRUE", "1", "yes", " true "])
def test_explicit_true_values(raw):
    assert config.parse_anthropic_trust_env(raw, "production") is True


@pytest.mark.parametrize("raw", ["false", "FALSE", "0", "no", ""])
def test_explicit_false_values(raw):
    assert config.parse_anthropic_trust_env(raw, "development") is False


# --- factory behavior ---------------------------------------------------------


def test_factory_passes_trust_env_true(monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_TRUST_ENV", True)
    client = create_anthropic_client()
    try:
        assert client.trust_env is True
    finally:
        import asyncio

        asyncio.run(client.aclose())


def test_factory_passes_trust_env_false(monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_TRUST_ENV", False)
    client = create_anthropic_client()
    try:
        assert client.trust_env is False
    finally:
        import asyncio

        asyncio.run(client.aclose())


def test_factory_default_timeout_is_180_seconds(monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_TRUST_ENV", False)
    client = create_anthropic_client()
    try:
        assert client.timeout == httpx.Timeout(180.0)
    finally:
        import asyncio

        asyncio.run(client.aclose())


def test_factory_does_not_pass_proxy(monkeypatch):
    """proxy=None must no longer be passed programmatically anywhere."""
    captured_kwargs = {}
    real_client = httpx.AsyncClient

    def spy(*args, **kwargs):
        captured_kwargs.update(kwargs)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", spy)
    monkeypatch.setattr(config, "ANTHROPIC_TRUST_ENV", False)
    client = create_anthropic_client()
    try:
        assert "proxy" not in captured_kwargs
        assert captured_kwargs["trust_env"] is False
    finally:
        import asyncio

        asyncio.run(client.aclose())


# --- call sites use the shared factory ----------------------------------------


def test_generation_uses_factory():
    source = inspect.getsource(claude_service)
    assert "create_anthropic_client()" in source
    assert "trust_env=False" not in source
    assert "proxy=None" not in source


def test_replacement_uses_factory():
    source = inspect.getsource(replacement_service)
    assert "create_anthropic_client()" in source
    assert "trust_env=False" not in source
    assert "proxy=None" not in source
