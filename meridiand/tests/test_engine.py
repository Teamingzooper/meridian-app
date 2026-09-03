"""Tests for the engine's loop lifecycle.

A dead loop used to turn every later call into 'Event loop is closed' forever,
while the sidecar kept answering /health — so the app attached to a helper that
could no longer reach a device.
"""
import asyncio

import pytest

from meridiand.engine import Engine


@pytest.fixture
def engine():
    made = Engine(tick_hz=50.0)
    made.start()
    yield made
    made.shutdown()


class TestLoopLifecycle:
    def test_starts_a_live_loop(self, engine):
        assert engine._loop_alive

    def test_submits_work_to_the_loop(self, engine):
        async def answer():
            return 41 + 1
        assert engine._submit(answer()) == 42

    def test_status_works_without_a_device(self, engine):
        assert engine.status()["engine"] == "running"

    def test_recovers_after_the_loop_dies(self, engine):
        # Kill the loop the way a crash would, behind the engine's back.
        loop = engine._loop
        loop.call_soon_threadsafe(loop.stop)
        for _ in range(200):
            if not engine._loop_alive:
                break
            asyncio_sleep = 0.01
            import time; time.sleep(asyncio_sleep)

        async def answer():
            return "recovered"

        # The call must succeed rather than raise 'Event loop is closed'.
        assert engine._submit(answer()) == "recovered"
        assert engine._loop_alive

    def test_submitting_before_start_is_an_error(self):
        cold = Engine()
        async def answer():
            return 1
        with pytest.raises(RuntimeError, match="not started"):
            cold._submit(answer())
