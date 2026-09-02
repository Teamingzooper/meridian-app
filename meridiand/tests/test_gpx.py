"""Tests for GPX reading and writing."""
import pytest

from meridiand.geo import Coord
from meridiand.gpx import MAX_GPX_BYTES, GpxError, parse_gpx, write_gpx

TRACK = """<?xml version="1.0"?>
<gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">
  <trk><name>Morning run</name><trkseg>
    <trkpt lat="51.5074" lon="-0.1278"/>
    <trkpt lat="51.5080" lon="-0.1290"/>
  </trkseg></trk>
</gpx>"""

NO_NAMESPACE = """<?xml version="1.0"?>
<gpx version="1.1">
  <trk><trkseg><trkpt lat="1.0" lon="2.0"/><trkpt lat="3.0" lon="4.0"/></trkseg></trk>
</gpx>"""

ROUTE_ONLY = """<gpx xmlns="http://www.topografix.com/GPX/1/1">
  <rte><name>Commute</name>
    <rtept lat="10.0" lon="20.0"/><rtept lat="11.0" lon="21.0"/>
  </rte>
</gpx>"""

WAYPOINTS_ONLY = """<gpx xmlns="http://www.topografix.com/GPX/1/1">
  <wpt lat="5.0" lon="6.0"/><wpt lat="7.0" lon="8.0"/>
</gpx>"""


class TestParsing:
    def test_reads_a_track(self):
        route = parse_gpx(TRACK)
        assert route.points == [Coord(51.5074, -0.1278), Coord(51.5080, -0.1290)]

    def test_reads_the_track_name(self):
        assert parse_gpx(TRACK).name == "Morning run"

    def test_handles_files_without_a_namespace(self):
        assert parse_gpx(NO_NAMESPACE).points == [Coord(1.0, 2.0), Coord(3.0, 4.0)]

    def test_falls_back_to_routes(self):
        route = parse_gpx(ROUTE_ONLY)
        assert route.points == [Coord(10.0, 20.0), Coord(11.0, 21.0)]
        assert route.name == "Commute"

    def test_falls_back_to_loose_waypoints(self):
        assert parse_gpx(WAYPOINTS_ONLY).points == [Coord(5.0, 6.0), Coord(7.0, 8.0)]

    def test_prefers_a_track_over_a_route_in_the_same_file(self):
        both = TRACK.replace("</gpx>", '<rte><rtept lat="0" lon="0"/></rte></gpx>')
        assert parse_gpx(both).points[0] == Coord(51.5074, -0.1278)

    def test_joins_multiple_segments_in_order(self):
        multi = """<gpx><trk><trkseg><trkpt lat="1" lon="1"/></trkseg>
                   <trkseg><trkpt lat="2" lon="2"/></trkseg></trk></gpx>"""
        assert parse_gpx(multi).points == [Coord(1.0, 1.0), Coord(2.0, 2.0)]

    def test_names_default_when_absent(self):
        assert parse_gpx(NO_NAMESPACE).name == "Imported route"

    def test_len_reports_point_count(self):
        assert len(parse_gpx(TRACK)) == 2


class TestBadInput:
    def test_rejects_malformed_xml(self):
        with pytest.raises(GpxError, match="not valid GPX"):
            parse_gpx("<gpx><trk>")

    def test_rejects_a_file_with_no_points(self):
        with pytest.raises(GpxError, match="no usable points"):
            parse_gpx('<gpx xmlns="http://www.topografix.com/GPX/1/1"></gpx>')

    def test_skips_points_with_missing_coordinates(self):
        mixed = '<gpx><trk><trkseg><trkpt lat="1"/><trkpt lat="2" lon="3"/></trkseg></trk></gpx>'
        assert parse_gpx(mixed).points == [Coord(2.0, 3.0)]

    def test_skips_points_outside_the_valid_range(self):
        bad = '<gpx><trk><trkseg><trkpt lat="999" lon="0"/><trkpt lat="1" lon="2"/></trkseg></trk></gpx>'
        assert parse_gpx(bad).points == [Coord(1.0, 2.0)]

    def test_skips_unparseable_numbers(self):
        bad = '<gpx><trk><trkseg><trkpt lat="north" lon="0"/><trkpt lat="1" lon="2"/></trkseg></trk></gpx>'
        assert parse_gpx(bad).points == [Coord(1.0, 2.0)]

    def test_rejects_an_oversized_document(self):
        with pytest.raises(GpxError, match="too large"):
            parse_gpx("x" * (MAX_GPX_BYTES + 1))


class TestWriting:
    points = [Coord(51.5074, -0.1278), Coord(48.8584, 2.2945)]

    def test_writes_a_gpx_header(self):
        out = write_gpx(self.points)
        assert out.startswith("<?xml")
        assert 'version="1.1"' in out
        assert "topografix" in out

    def test_includes_every_point(self):
        out = write_gpx(self.points)
        assert out.count("<trkpt") == 2

    def test_carries_the_name(self):
        assert "<name>Weekend loop</name>" in write_gpx(self.points, "Weekend loop")

    def test_escapes_names_that_would_break_the_xml(self):
        out = write_gpx(self.points, 'Tom & "Jerry" <trip>')
        assert "&amp;" in out and "&lt;trip&gt;" in out
        # Still parses, which is the point of escaping.
        assert len(parse_gpx(out)) == 2

    def test_refuses_to_write_an_empty_route(self):
        with pytest.raises(GpxError):
            write_gpx([])

    def test_accepts_any_iterable(self):
        assert write_gpx(iter(self.points)).count("<trkpt") == 2


class TestRoundTrip:
    def test_survives_a_write_then_read(self):
        original = [Coord(51.5074, -0.1278), Coord(48.8584, 2.2945), Coord(-33.8688, 151.2093)]
        parsed = parse_gpx(write_gpx(original, "Trip"))
        assert parsed.name == "Trip"
        for before, after in zip(original, parsed.points):
            assert after.lat == pytest.approx(before.lat, abs=1e-6)
            assert after.lon == pytest.approx(before.lon, abs=1e-6)

    def test_preserves_point_order(self):
        original = [Coord(float(i), float(i)) for i in range(10)]
        assert parse_gpx(write_gpx(original)).points == original
