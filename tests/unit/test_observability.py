"""Unit tests for optional Langfuse tracing. No Langfuse connection required."""

import sys
import types

import pytest

from siivila.observability import observability_enabled, trace_span

ENV = {"LANGFUSE_SECRET_KEY": "sk-test", "LANGFUSE_PUBLIC_KEY": "pk-test"}


class TestDisabled:
    def test_no_env_vars_means_disabled(self, monkeypatch):
        monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
        monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
        assert observability_enabled() is False

    def test_span_is_noop_and_langfuse_never_imported(self, monkeypatch):
        for var in ENV:
            monkeypatch.delenv(var, raising=False)
        monkeypatch.delitem(sys.modules, "langfuse", raising=False)
        with trace_span("test") as span:
            assert span is None
        assert "langfuse" not in sys.modules


class TestEnabled:
    def test_env_vars_enable(self, monkeypatch):
        for var, value in ENV.items():
            monkeypatch.setenv(var, value)
        assert observability_enabled() is True

    def test_span_uses_langfuse_client(self, monkeypatch):
        for var, value in ENV.items():
            monkeypatch.setenv(var, value)

        entered = []

        class _Span:
            def __enter__(self):
                entered.append(True)
                return "the-span"

            def __exit__(self, *exc):
                return False

        class _Client:
            def start_as_current_span(self, name):
                assert name == "health-check"
                return _Span()

        fake = types.ModuleType("langfuse")
        fake.get_client = lambda: _Client()
        monkeypatch.setitem(sys.modules, "langfuse", fake)

        with trace_span("health-check") as span:
            assert span == "the-span"
        assert entered == [True]

    def test_missing_package_warns_and_noops(self, monkeypatch):
        for var, value in ENV.items():
            monkeypatch.setenv(var, value)
        monkeypatch.setitem(sys.modules, "langfuse", None)  # import fails
        with pytest.warns(UserWarning, match="not installed"):
            with trace_span("test") as span:
                assert span is None
