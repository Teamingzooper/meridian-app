import CoreLocation
import Foundation

/// Recognises a location pasted as text.
///
/// People copy coordinates from wildly different places — a Maps share sheet, a
/// spreadsheet, a bug report — so this accepts the common shapes rather than
/// insisting on one. Anything it cannot read returns nil and falls through to a
/// normal place-name search.
enum CoordinateParser {

    /// A decimal pair, optionally with degree signs and hemisphere letters.
    ///
    /// Matches "48.8584, 2.2945", "48.8584 2.2945" and "48.8584° N, 2.2945° E".
    private static let pairPattern = try? NSRegularExpression(
        pattern: #"(-?\d{1,3}(?:\.\d+)?)\s*°?\s*([NSns])?\s*[,\s]\s*(-?\d{1,3}(?:\.\d+)?)\s*°?\s*([EWew])?"#
    )

    static func parse(_ text: String) -> CLLocationCoordinate2D? {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return nil }

        if let fromURL = parseURL(trimmed) { return fromURL }
        return parsePair(trimmed)
    }

    // MARK: - Bare pairs

    private static func parsePair(_ text: String) -> CLLocationCoordinate2D? {
        guard let pairPattern,
              let match = pairPattern.firstMatch(
                in: text, range: NSRange(text.startIndex..., in: text)
              )
        else { return nil }

        func group(_ index: Int) -> String? {
            guard let range = Range(match.range(at: index), in: text) else { return nil }
            return String(text[range])
        }

        guard let latitudeText = group(1), var latitude = Double(latitudeText),
              let longitudeText = group(3), var longitude = Double(longitudeText)
        else { return nil }

        // "48.85 S" means -48.85; a leading minus with S would be contradictory,
        // so the hemisphere letter only ever sets the sign, never flips it.
        if let hemisphere = group(2)?.uppercased(), hemisphere == "S" {
            latitude = -abs(latitude)
        }
        if let hemisphere = group(4)?.uppercased(), hemisphere == "W" {
            longitude = -abs(longitude)
        }

        return validated(latitude, longitude)
    }

    // MARK: - Map links

    private static func parseURL(_ text: String) -> CLLocationCoordinate2D? {
        guard text.lowercased().hasPrefix("http") || text.lowercased().hasPrefix("geo:")
        else { return nil }

        // geo:48.8584,2.2945 — the whole payload is the pair.
        if text.lowercased().hasPrefix("geo:") {
            return parsePair(String(text.dropFirst(4)))
        }

        guard let components = URLComponents(string: text) else { return nil }

        // Apple Maps and most share links put the pair in a query item.
        for name in ["ll", "sll", "q", "daddr", "center"] {
            if let value = components.queryItems?.first(where: { $0.name == name })?.value,
               let coordinate = parsePair(value) {
                return coordinate
            }
        }

        // Google Maps encodes the viewport in the path: /maps/@48.8584,2.2945,15z
        if let atRange = components.path.range(of: "@") {
            let tail = components.path[atRange.upperBound...]
            let pair = tail.split(separator: ",").prefix(2).joined(separator: ",")
            if let coordinate = parsePair(pair) { return coordinate }
        }

        return nil
    }

    private static func validated(_ latitude: Double, _ longitude: Double)
        -> CLLocationCoordinate2D? {
        guard (-90...90).contains(latitude), (-180...180).contains(longitude) else { return nil }
        return CLLocationCoordinate2D(latitude: latitude, longitude: longitude)
    }
}
