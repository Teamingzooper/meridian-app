"""Tests for pause/resume bookkeeping. Time is injected, never read."""
import pytest

from meridiand.geo import Coord, total_distance
from meridiand.playback import Playback
from meridiand.route import RoutePlayer

LINE = [Coord(0.0, 0.0), Coord(0.0, 1.0)]
LINE_M = total_distance(LINE)


def make(speed=100.0, loop=False, now=0.0):
    return Playback(RoutePlayer(LINE, speed_mps=speed, loop=loop), now=now)


class TestElapsed:
    def test_starts_at_zero(self):
        assert make(now=1000.0).elapsed(1000.0) == pytest.approx(0.0)

    def test_advances_with_the_clock(self):
        pb = make(now=100.0)
        assert pb.elapsed(160.0) == pytest.approx(60.0)

    def test_running_by_default(self):
        assert not make().is_paused

    def test_a_clock_that_goes_backwards_does_not_rewind_progress(self):
        pb = make(now=100.0)
        assert pb.elapsed(90.0) == pytest.approx(0.0)


class TestPausing:
    def test_freezes_elapsed_time(self):
        pb = make(now=0.0)
        pb.pause(30.0)
        assert pb.elapsed(30.0) == pytest.approx(30.0)
        assert pb.elapsed(500.0) == pytest.approx(30.0)

    def test_reports_paused(self):
        pb = make(now=0.0)
        pb.pause(10.0)
        assert pb.is_paused

    def test_pausing_twice_does_not_double_count(self):
        pb = make(now=0.0)
        pb.pause(30.0)
        pb.pause(90.0)
        assert pb.elapsed(200.0) == pytest.approx(30.0)

    def test_position_holds_still_while_paused(self):
        pb = make(now=0.0)
        pb.pause(30.0)
        assert pb.position(30.0) == pb.position(9999.0)


class TestResuming:
    def test_continues_from_where_it_paused(self):
        pb = make(now=0.0)
        pb.pause(30.0)
        pb.resume(100.0)
        # 30s before the pause, then 20s after resuming.
        assert pb.elapsed(120.0) == pytest.approx(50.0)

    def test_time_spent_paused_is_excluded(self):
        pb = make(now=0.0)
        pb.pause(10.0)
        pb.resume(1000.0)
        assert pb.elapsed(1010.0) == pytest.approx(20.0)

    def test_resuming_while_running_is_a_no_op(self):
        pb = make(now=0.0)
        pb.resume(50.0)
        assert pb.elapsed(100.0) == pytest.approx(100.0)

    def test_survives_several_pause_resume_cycles(self):
        pb = make(now=0.0)
        for start, stop in [(10.0, 20.0), (30.0, 40.0), (50.0, 60.0)]:
            pb.pause(start)
            pb.resume(stop)
            # each cycle contributes 10s of running time before the pause
        assert pb.elapsed(70.0) == pytest.approx(40.0)


class TestSeek:
    def test_jumps_to_a_fraction(self):
        pb = make(now=0.0)
        pb.seek(0.5, now=0.0)
        assert pb.progress(0.0) == pytest.approx(0.5)

    def test_clamps_out_of_range_values(self):
        pb = make(now=0.0)
        pb.seek(5.0, now=0.0)
        assert pb.progress(0.0) == pytest.approx(1.0)
        pb.seek(-2.0, now=0.0)
        assert pb.progress(0.0) == pytest.approx(0.0)

    def test_keeps_running_after_seeking(self):
        pb = make(now=0.0)
        pb.seek(0.5, now=0.0)
        assert not pb.is_paused
        assert pb.progress(pb.player.duration_s / 2) == pytest.approx(1.0)

    def test_stays_paused_after_seeking(self):
        pb = make(now=0.0)
        pb.pause(5.0)
        pb.seek(0.25, now=5.0)
        assert pb.is_paused
        assert pb.progress(9999.0) == pytest.approx(0.25)


class TestCompletion:
    def test_finishes_at_the_end(self):
        pb = make(now=0.0)
        assert pb.is_finished(pb.player.duration_s)

    def test_not_finished_partway(self):
        pb = make(now=0.0)
        assert not pb.is_finished(pb.player.duration_s / 2)

    def test_pausing_prevents_completion(self):
        pb = make(now=0.0)
        pb.pause(1.0)
        assert not pb.is_finished(99_999.0)

    def test_a_looping_route_never_finishes(self):
        pb = make(loop=True, now=0.0)
        assert not pb.is_finished(99_999.0)


class TestPosition:
    def test_moves_along_the_route(self):
        pb = make(speed=1000.0, now=0.0)
        assert pb.position(0.0).lon < pb.position(30.0).lon

    def test_reaches_the_end(self):
        pb = make(now=0.0)
        assert pb.position(pb.player.duration_s).lon == pytest.approx(1.0, abs=1e-6)
