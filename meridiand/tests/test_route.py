"""Tests for route playback. Time is passed in, never read from a clock."""
import pytest

from meridiand.geo import Coord, total_distance
from meridiand.route import SPEED_PRESETS, RoutePlayer

# A due-east line along the equator: 1 degree of longitude ~= 111,195 m.
LINE = [Coord(0.0, 0.0), Coord(0.0, 1.0)]
LINE_M = total_distance(LINE)


class TestConstruction:
    def test_rejects_empty_route(self):
        with pytest.raises(ValueError):
            RoutePlayer([], speed_mps=1.4)

    def test_rejects_zero_speed(self):
        with pytest.raises(ValueError):
            RoutePlayer(LINE, speed_mps=0)

    def test_rejects_negative_speed(self):
        with pytest.raises(ValueError):
            RoutePlayer(LINE, speed_mps=-3)

    def test_accepts_a_single_point(self):
        player = RoutePlayer([Coord(1.0, 2.0)], speed_mps=1.4)
        assert player.duration_s == 0.0


class TestGeometry:
    def test_length_matches_the_polyline(self):
        assert RoutePlayer(LINE, speed_mps=1.4).length_m == pytest.approx(LINE_M)

    def test_duration_is_length_over_speed(self):
        player = RoutePlayer(LINE, speed_mps=10.0)
        assert player.duration_s == pytest.approx(LINE_M / 10.0)

    def test_faster_speed_means_shorter_duration(self):
        slow = RoutePlayer(LINE, speed_mps=1.4).duration_s
        fast = RoutePlayer(LINE, speed_mps=13.4).duration_s
        assert fast < slow


class TestPositionOverTime:
    def test_starts_at_the_first_point(self):
        assert RoutePlayer(LINE, speed_mps=10.0).position_at(0.0) == LINE[0]

    def test_negative_time_clamps_to_the_start(self):
        assert RoutePlayer(LINE, speed_mps=10.0).position_at(-5.0) == LINE[0]

    def test_reaches_the_end_at_its_duration(self):
        player = RoutePlayer(LINE, speed_mps=10.0)
        assert player.position_at(player.duration_s).lon == pytest.approx(1.0, abs=1e-6)

    def test_travels_the_expected_distance_each_second(self):
        player = RoutePlayer(LINE, speed_mps=100.0)
        p = player.position_at(60.0)
        assert total_distance([LINE[0], p]) == pytest.approx(6000.0, rel=1e-3)

    def test_advances_monotonically(self):
        player = RoutePlayer(LINE, speed_mps=1000.0)
        lons = [player.position_at(t).lon for t in range(0, 120, 5)]
        assert lons == sorted(lons)

    def test_a_single_point_route_never_moves(self):
        here = Coord(51.5, -0.12)
        player = RoutePlayer([here], speed_mps=1.4)
        assert player.position_at(0.0) == here
        assert player.position_at(9999.0) == here


class TestFinishing:
    def test_holds_at_the_end_once_complete(self):
        player = RoutePlayer(LINE, speed_mps=10.0)
        past_end = player.position_at(player.duration_s * 3)
        assert past_end.lon == pytest.approx(1.0, abs=1e-6)

    def test_not_finished_midway(self):
        player = RoutePlayer(LINE, speed_mps=10.0)
        assert not player.is_finished(player.duration_s / 2)

    def test_finished_at_its_duration(self):
        player = RoutePlayer(LINE, speed_mps=10.0)
        assert player.is_finished(player.duration_s)

    def test_a_looping_route_never_finishes(self):
        player = RoutePlayer(LINE, speed_mps=10.0, loop=True)
        assert not player.is_finished(player.duration_s * 10)

    def test_a_zero_length_route_is_immediately_finished(self):
        player = RoutePlayer([Coord(0.0, 0.0), Coord(0.0, 0.0)], speed_mps=1.4)
        assert player.is_finished(0.0)


class TestLooping:
    def test_wraps_back_to_the_start(self):
        player = RoutePlayer(LINE, speed_mps=10.0, loop=True)
        assert player.position_at(player.duration_s).lon == pytest.approx(0.0, abs=1e-6)

    def test_one_and_a_half_laps_lands_midway(self):
        player = RoutePlayer(LINE, speed_mps=10.0, loop=True)
        p = player.position_at(player.duration_s * 1.5)
        assert p.lon == pytest.approx(0.5, abs=1e-3)

    def test_a_zero_length_looping_route_does_not_divide_by_zero(self):
        player = RoutePlayer([Coord(4.0, 5.0)], speed_mps=1.4, loop=True)
        assert player.position_at(1234.0) == Coord(4.0, 5.0)


class TestProgress:
    def test_runs_zero_to_one(self):
        player = RoutePlayer(LINE, speed_mps=10.0)
        assert player.progress_at(0.0) == pytest.approx(0.0)
        assert player.progress_at(player.duration_s) == pytest.approx(1.0)

    def test_clamps_past_the_end(self):
        player = RoutePlayer(LINE, speed_mps=10.0)
        assert player.progress_at(player.duration_s * 5) == pytest.approx(1.0)

    def test_halfway(self):
        player = RoutePlayer(LINE, speed_mps=10.0)
        assert player.progress_at(player.duration_s / 2) == pytest.approx(0.5)


class TestSpeedPresets:
    def test_covers_the_three_advertised_modes(self):
        assert {"walk", "bike", "drive"} <= SPEED_PRESETS.keys()

    def test_ordered_slowest_to_fastest(self):
        assert SPEED_PRESETS["walk"] < SPEED_PRESETS["bike"] < SPEED_PRESETS["drive"]

    def test_walking_pace_is_plausible(self):
        assert 1.0 <= SPEED_PRESETS["walk"] <= 2.0
