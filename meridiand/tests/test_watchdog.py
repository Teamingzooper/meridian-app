"""Tests for the parent watchdog."""
import os
import threading
import time

from meridiand.watchdog import process_is_alive, watch_parent


class TestProcessIsAlive:
    def test_our_own_process_is_alive(self):
        assert process_is_alive(os.getpid())

    def test_an_impossible_pid_is_not(self):
        # Well above any real pid, and never allocated.
        assert not process_is_alive(2_000_000_000)

    def test_pid_1_counts_as_alive_even_though_we_cannot_signal_it(self):
        # PermissionError means it exists but is not ours; that is still alive.
        assert process_is_alive(1)


class TestWatchParent:
    def test_calls_back_once_the_parent_disappears(self):
        fired = threading.Event()
        alive = {"value": True}

        watch_parent(
            1234, on_exit=fired.set, interval=0.01,
            is_alive=lambda _: alive["value"],
        )
        time.sleep(0.05)
        assert not fired.is_set(), "fired while the parent was still alive"

        alive["value"] = False
        assert fired.wait(timeout=2.0), "did not fire after the parent exited"

    def test_stays_quiet_while_the_parent_lives(self):
        fired = threading.Event()
        watch_parent(1234, on_exit=fired.set, interval=0.01, is_alive=lambda _: True)
        assert not fired.wait(timeout=0.2)

    def test_cancelling_stops_the_watch(self):
        fired = threading.Event()
        cancel = watch_parent(1234, on_exit=fired.set, interval=0.01, is_alive=lambda _: False)
        cancel.set()
        assert not fired.wait(timeout=0.2)

    def test_it_fires_only_once(self):
        calls = []
        watch_parent(1234, on_exit=lambda: calls.append(1), interval=0.01,
                     is_alive=lambda _: False)
        time.sleep(0.15)
        assert len(calls) == 1
