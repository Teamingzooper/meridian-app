"""Exit when the app that started us goes away.

An orphaned sidecar keeps answering `/health` and keeps holding the port, so the
next app to launch attaches to it instead of starting a fresh one. If that
orphan is stale or broken, the new app inherits the fault and nothing about the
symptom points at the cause.

Tying the sidecar's lifetime to its parent removes that whole class of problem.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Callable

logger = logging.getLogger(__name__)

CHECK_INTERVAL_S = 3.0


def process_is_alive(pid: int) -> bool:
    """True if `pid` still exists. Signal 0 checks without delivering anything."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Owned by someone else, which still means it exists.
        return True
    return True


def watch_parent(
    pid: int,
    on_exit: Callable[[], None],
    interval: float = CHECK_INTERVAL_S,
    is_alive: Callable[[int], bool] = process_is_alive,
) -> threading.Event:
    """Call `on_exit` once `pid` disappears. Returns a handle to cancel the watch."""
    cancelled = threading.Event()

    def loop() -> None:
        while not cancelled.wait(interval):
            if not is_alive(pid):
                logger.info("parent process %d exited; shutting down", pid)
                on_exit()
                return

    threading.Thread(target=loop, name="meridian-watchdog", daemon=True).start()
    return cancelled
