"""Tests for the pure geodesic math. No device, no clock, no I/O."""
import math

import pytest

from meridiand.geo import (
    Coord,
    bearing,
    densify,
    haversine,
    jitter,
    point_at_distance,
    total_distance,
)

SF = Coord(37.7749, -122.4194)
NYC = Coord(40.7128, -74.0060)


class TestHaversine:
    def test_zero_for_identical_points(self):
        assert haversine(SF, SF) == pytest.approx(0.0, abs=1e-9)

    def test_one_degree_of_latitude_is_about_111km(self):
        d = haversine(Coord(0.0, 0.0), Coord(1.0, 0.0))
        assert d == pytest.approx(111_195, rel=0.001)

    def test_known_city_pair(self):
        # SF -> NYC great-circle is ~4130 km.
        assert haversine(SF, NYC) == pytest.approx(4_130_000, rel=0.01)

    def test_symmetric(self):
        assert haversine(SF, NYC) == pytest.approx(haversine(NYC, SF))

    def test_longitude_degree_shrinks_with_latitude(self):
        at_equator = haversine(Coord(0.0, 0.0), Coord(0.0, 1.0))
        at_sixty = haversine(Coord(60.0, 0.0), Coord(60.0, 1.0))
        # cos(60 deg) == 0.5, so a degree of longitude is half as wide.
        assert at_sixty == pytest.approx(at_equator * 0.5, rel=0.01)


class TestBearing:
    def test_due_north_is_zero(self):
        assert bearing(Coord(0.0, 0.0), Coord(1.0, 0.0)) == pytest.approx(0.0, abs=0.01)

    def test_due_east_is_ninety(self):
        assert bearing(Coord(0.0, 0.0), Coord(0.0, 1.0)) == pytest.approx(90.0, abs=0.01)

    def test_due_south_is_one_eighty(self):
        assert bearing(Coord(1.0, 0.0), Coord(0.0, 0.0)) == pytest.approx(180.0, abs=0.01)

    def test_always_in_zero_to_360(self):
        assert 0 <= bearing(Coord(0.0, 0.0), Coord(-1.0, -1.0)) < 360


class TestTotalDistance:
    def test_empty_and_single_point_are_zero(self):
        assert total_distance([]) == 0.0
        assert total_distance([SF]) == 0.0

    def test_sums_segments(self):
        a, b, c = Coord(0.0, 0.0), Coord(0.0, 1.0), Coord(0.0, 2.0)
        assert total_distance([a, b, c]) == pytest.approx(
            haversine(a, b) + haversine(b, c)
        )


class TestPointAtDistance:
    line = [Coord(0.0, 0.0), Coord(0.0, 1.0), Coord(0.0, 2.0)]

    def test_zero_returns_first_point(self):
        assert point_at_distance(self.line, 0.0) == self.line[0]

    def test_full_length_returns_last_point(self):
        p = point_at_distance(self.line, total_distance(self.line))
        assert p.lat == pytest.approx(self.line[-1].lat, abs=1e-6)
        assert p.lon == pytest.approx(self.line[-1].lon, abs=1e-6)

    def test_beyond_end_clamps_to_last_point(self):
        p = point_at_distance(self.line, 1e9)
        assert p.lon == pytest.approx(2.0, abs=1e-6)

    def test_negative_clamps_to_first_point(self):
        assert point_at_distance(self.line, -50.0) == self.line[0]

    def test_halfway_lands_at_the_middle_vertex(self):
        half = total_distance(self.line) / 2
        p = point_at_distance(self.line, half)
        assert p.lon == pytest.approx(1.0, abs=1e-4)

    def test_quarter_way_is_inside_the_first_segment(self):
        quarter = total_distance(self.line) / 4
        p = point_at_distance(self.line, quarter)
        assert p.lon == pytest.approx(0.5, abs=1e-3)

    def test_single_point_route_always_returns_it(self):
        assert point_at_distance([SF], 100.0) == SF

    def test_empty_route_raises(self):
        with pytest.raises(ValueError):
            point_at_distance([], 0.0)

    def test_walking_the_line_advances_monotonically(self):
        total = total_distance(self.line)
        lons = [point_at_distance(self.line, total * f / 20).lon for f in range(21)]
        assert lons == sorted(lons)


class TestDensify:
    def test_respects_spacing(self):
        line = [Coord(0.0, 0.0), Coord(0.0, 1.0)]
        pts = densify(line, spacing_m=10_000)
        gaps = [haversine(a, b) for a, b in zip(pts, pts[1:])]
        # Every gap is the requested spacing, except a shorter final remainder.
        assert all(g == pytest.approx(10_000, rel=0.02) for g in gaps[:-1])
        assert gaps[-1] <= 10_000 * 1.02

    def test_always_includes_both_endpoints(self):
        line = [Coord(0.0, 0.0), Coord(0.0, 1.0)]
        pts = densify(line, spacing_m=10_000)
        assert pts[0] == line[0]
        assert pts[-1].lon == pytest.approx(1.0, abs=1e-6)

    def test_short_route_returns_endpoints_only(self):
        line = [Coord(0.0, 0.0), Coord(0.0, 0.00001)]
        assert len(densify(line, spacing_m=10_000)) == 2

    def test_rejects_nonpositive_spacing(self):
        with pytest.raises(ValueError):
            densify([Coord(0.0, 0.0), Coord(0.0, 1.0)], spacing_m=0)


class TestJitter:
    def test_stays_within_requested_radius(self):
        for _ in range(200):
            p = jitter(SF, radius_m=5.0)
            assert haversine(SF, p) <= 5.0 + 1e-6

    def test_zero_radius_is_a_no_op(self):
        assert jitter(SF, radius_m=0.0) == SF

    def test_actually_moves_the_point(self):
        moved = [jitter(SF, radius_m=5.0) for _ in range(50)]
        assert any(p != SF for p in moved)

    def test_rejects_negative_radius(self):
        with pytest.raises(ValueError):
            jitter(SF, radius_m=-1.0)
