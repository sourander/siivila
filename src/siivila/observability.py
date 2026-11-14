"""Optional LLM-call observability (Langfuse) for local development.

Tracing activates only when the Langfuse environment variables are set and
the optional `langfuse` package is installed (`uv sync --extra observability`).
Otherwise every trace span is a no-op and no connection is attempted.
"""

import os
import warnings
from collections.abc import Iterator
from contextlib import contextmanager

_REQUIRED_ENV_VARS = ("LANGFUSE_SECRET_KEY", "LANGFUSE_PUBLIC_KEY")


def observability_enabled() -> bool:
    """True when the environment asks for tracing."""
    return all(os.environ.get(var) for var in _REQUIRED_ENV_VARS)


@contextmanager
def trace_span(name: str) -> Iterator[object]:
    """Trace one LLM interaction; yields a span object or None.

    Never raises for missing configuration: observability must not be able
    to break an analysis run.
    """
    if not observability_enabled():
        yield None
        return
    try:
        from langfuse import get_client
    except ImportError:
        warnings.warn(
            "Langfuse environment variables are set but the 'langfuse' package "
            "is not installed; tracing is disabled. "
            "Install with: uv sync --extra observability",
            stacklevel=2,
        )
        yield None
        return
    client = get_client()
    with client.start_as_current_span(name=name) as span:
        yield span
