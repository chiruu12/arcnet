"""Shared TabFM test helpers — deterministic degrade path, no real weight loads."""

from __future__ import annotations

import functools
import importlib.util
import signal
import sys
from contextlib import contextmanager
from typing import Any, Callable, Iterator, TypeVar
from unittest.mock import MagicMock, patch

F = TypeVar("F", bound=Callable[..., Any])

TABFM_INSTALLED = importlib.util.find_spec("tabfm") is not None


class TestTimeoutError(AssertionError):
    """Raised when a guarded test exceeds its wall-clock budget."""


def timeout_seconds(seconds: float) -> Callable[[F], F]:
    """Fail fast if a test blocks (e.g. accidental model download). Unix main thread only."""

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not hasattr(signal, "SIGALRM"):
                return fn(*args, **kwargs)

            def _on_alarm(signum: int, frame: Any) -> None:
                raise TestTimeoutError(f"{fn.__qualname__} exceeded {seconds}s (possible TabFM hang)")

            previous = signal.signal(signal.SIGALRM, _on_alarm)
            signal.setitimer(signal.ITIMER_REAL, seconds)
            try:
                return fn(*args, **kwargs)
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
                signal.signal(signal.SIGALRM, previous)

        return wrapper  # type: ignore[return-value]

    return decorator


@contextmanager
def patch_tabfm_unavailable(*, load_error: str = "missing weights") -> Iterator[None]:
    """Force ``backend='tabfm'`` through the model-load failure / MAD-degrade path."""
    fake_tabfm = MagicMock()
    fake_tabfm.TabFMRegressor = MagicMock()
    with (
        patch.dict(sys.modules, {"tabfm": fake_tabfm}),
        patch(
            "arcnet_server.tabfm_worker._load_tabfm_model",
            side_effect=RuntimeError(load_error),
        ),
    ):
        yield
