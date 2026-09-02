"""Tests for the motion profile: easing, corners and wobble."""
import pytest

from meridiand.geo import Coord, total_distance
from meridiand.motion import MIN_SPEED_FACTOR, MotionProfile

# Due east along the equator, ~1112 m.
STRAIGHT = [Coord(0.0, 0.0), Coord(0.0, 0.01)]
# A right-angle turn: east then north.
CORNER = [Coord(0.0, 0.0), Coord(0.0, 0.01), Coord(0.01, 0.01)]


def profile(coords=STRAIGHT, **kwargs):
    kwargs.setdefault("cruise_mps", 1.4)
    return MotionProfile(coords, **kwargs)


class TestConstruction:
    def test_rejects_a_nonpositive_speed(self):
        with pytest.raises(ValueError):
            profile(cruise_mps=0)

    def test_rejects_absurd_wobble(self):
        with pytest.raises(ValueError):
            profile(wobble=1.5)

    def test_length_matches_the_polyline(self):
        assert profile().length_m == pytest.approx(total_distance(STRAIGHT))

    def test_a_zero_length_route_has_no_duration(self):
        assert profile([Coord(1.0, 1.0), Coord(1.0, 1.0)]).duration_s == 0.0


class TestSpeedShape:
    def test_starts_slow(self):
        assert profile().speed_factor_at(0.0) == pytest.approx(MIN_SPEED_FACTOR, abs=0.02)

    def test_ends_slow(self):
        p = profile()
        assert p.speed_factor_at(p.length_m) == pytest.approx(MIN_SPEED_FACTOR, abs=0.02)

    def test_reaches_full_speed_in_the_middle(self):
        p = profile()
        assert p.speed_factor_at(p.length_m / 2) > 0.9

    def test_never_stalls(self):
        p = profile(CORNER)
        for i in range(0, 101):
            assert p.speed_factor_at(p.length_m * i / 100) >= MIN_SPEED_FACTOR

    def test_never_wildly_exceeds_cruise(self):
        p = profile(wobble=0.07)
        for i in range(0, 101):
            assert p.speed_factor_at(p.length_m * i / 100) <= 1.08

    def test_easing_can_be_switched_off(self):
        p = profile(ease_m=0.0, wobble=0.0, corner_threshold_deg=180.0)
        assert p.speed_factor_at(0.0) == pytest.approx(1.0)
        assert p.speed_factor_at(p.length_m / 2) == pytest.approx(1.0)


class TestCorners:
    def test_slows_at_a_right_angle_turn(self):
        p = profile(CORNER, wobble=0.0)
        corner_distance = total_distance(CORNER[:2])
        at_corner = p.speed_factor_at(corner_distance)
        on_approach = p.speed_factor_at(corner_distance - 200)
        assert at_corner < on_approach

    def test_a_straight_route_has_no_corner_slowdown(self):
        p = profile(wobble=0.0)
        mid = p.speed_factor_at(p.length_m / 2)
        quarter = p.speed_factor_at(p.length_m / 4)
        assert mid == pytest.approx(quarter, abs=0.02)

    def test_repeated_points_do_not_break_bearing(self):
        # A zero-length leg has no bearing; it must not raise or produce a corner.
        repeated = [Coord(0.0, 0.0), Coord(0.0, 0.0), Coord(0.0, 0.01)]
        assert MotionProfile(repeated, cruise_mps=1.4).duration_s > 0


class TestTiming:
    def test_takes_longer_than_constant_speed(self):
        p = profile()
        assert p.duration_s > p.length_m / 1.4

    def test_but_not_absurdly_longer(self):
        p = profile()
        assert p.duration_s < (p.length_m / 1.4) * 1.5

    def test_faster_cruise_finishes_sooner(self):
        assert profile(cruise_mps=13.4).duration_s < profile(cruise_mps=1.4).duration_s


class TestDistanceLookup:
    def test_starts_at_zero(self):
        assert profile().distance_at(0.0) == 0.0

    def test_negative_time_is_the_start(self):
        assert profile().distance_at(-10.0) == 0.0

    def test_ends_at_the_full_length(self):
        p = profile()
        assert p.distance_at(p.duration_s) == pytest.approx(p.length_m)

    def test_past_the_end_clamps(self):
        p = profile()
        assert p.distance_at(p.duration_s * 5) == pytest.approx(p.length_m)

    def test_advances_monotonically(self):
        p = profile(CORNER)
        seen = [p.distance_at(p.duration_s * i / 60) for i in range(61)]
        assert seen == sorted(seen)

    def test_covers_less_ground_early_than_mid_route(self):
        # The easing is the point: the first stretch is slower than the middle.
        p = profile(wobble=0.0)
        slice_s = p.duration_s / 20
        early = p.distance_at(slice_s) - p.distance_at(0)
        middle = p.distance_at(p.duration_s / 2 + slice_s) - p.distance_at(p.duration_s / 2)
        assert early < middle


class TestPosition:
    def test_starts_at_the_first_point(self):
        assert profile().position_at(0.0) == STRAIGHT[0]

    def test_finishes_at_the_last_point(self):
        p = profile()
        assert p.position_at(p.duration_s).lon == pytest.approx(0.01, abs=1e-6)

    def test_moves_forward(self):
        p = profile()
        assert p.position_at(p.duration_s * 0.25).lon < p.position_at(p.duration_s * 0.75).lon
