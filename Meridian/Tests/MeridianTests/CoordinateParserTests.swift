import CoreLocation
import XCTest

@testable import Meridian

/// People paste locations from everywhere: a Maps share sheet, a spreadsheet, a
/// bug report. These are the shapes that actually turn up.
final class CoordinateParserTests: XCTestCase {

    private func assertParses(
        _ input: String, _ latitude: Double, _ longitude: Double,
        file: StaticString = #filePath, line: UInt = #line
    ) {
        guard let parsed = CoordinateParser.parse(input) else {
            return XCTFail("expected \(input) to parse", file: file, line: line)
        }
        XCTAssertEqual(parsed.latitude, latitude, accuracy: 1e-4, file: file, line: line)
        XCTAssertEqual(parsed.longitude, longitude, accuracy: 1e-4, file: file, line: line)
    }

    private func assertRejects(
        _ input: String, file: StaticString = #filePath, line: UInt = #line
    ) {
        XCTAssertNil(CoordinateParser.parse(input), "expected \(input) to be rejected",
                     file: file, line: line)
    }

    // MARK: - Plain pairs

    func testCommaSeparated() { assertParses("48.8584, 2.2945", 48.8584, 2.2945) }
    func testNoSpace() { assertParses("48.8584,2.2945", 48.8584, 2.2945) }
    func testSpaceSeparated() { assertParses("48.8584 2.2945", 48.8584, 2.2945) }
    func testNegatives() { assertParses("-33.8688, 151.2093", -33.8688, 151.2093) }
    func testSurroundingWhitespace() { assertParses("   51.5074, -0.1278  ", 51.5074, -0.1278) }
    func testIntegers() { assertParses("48, 2", 48, 2) }

    // MARK: - Degrees and hemispheres

    func testDegreeSigns() { assertParses("48.8584° N, 2.2945° E", 48.8584, 2.2945) }

    func testSouthAndWestBecomeNegative() {
        assertParses("33.8688 S, 151.2093 W", -33.8688, -151.2093)
    }

    func testLowercaseHemispheres() { assertParses("33.8688 s, 151.2093 w", -33.8688, -151.2093) }

    // MARK: - Links

    func testGeoURI() { assertParses("geo:48.8584,2.2945", 48.8584, 2.2945) }

    func testAppleMapsLink() {
        assertParses("https://maps.apple.com/?ll=48.8584,2.2945", 48.8584, 2.2945)
    }

    func testAppleMapsQuery() {
        assertParses("https://maps.apple.com/?q=51.5074,-0.1278", 51.5074, -0.1278)
    }

    func testGoogleMapsViewport() {
        assertParses("https://www.google.com/maps/@48.8584,2.2945,15z", 48.8584, 2.2945)
    }

    func testGoogleMapsPlace() {
        assertParses(
            "https://www.google.com/maps/place/Tokyo/@35.6762,139.6503,17z", 35.6762, 139.6503
        )
    }

    // MARK: - Rejections
    //
    // Rejecting cleanly matters as much as parsing: anything unrecognised has to
    // fall through to a place-name search rather than land somewhere wrong.

    func testPlaceNamesAreNotCoordinates() { assertRejects("Eiffel Tower") }
    func testEmptyInput() { assertRejects("") }
    func testWhitespaceOnly() { assertRejects("   ") }
    func testLatitudeOutOfRange() { assertRejects("91.0, 0.0") }
    func testLongitudeOutOfRange() { assertRejects("0.0, 181.0") }
    func testBothOutOfRange() { assertRejects("999, 999") }
    func testASingleNumberIsNotAPair() { assertRejects("48.8584") }
    func testAnUnrelatedLink() { assertRejects("https://example.com/about") }
}
