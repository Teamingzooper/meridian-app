import Foundation
import MapKit

/// Turns waypoints into a path that follows real streets.
///
/// MKDirections routes one pair at a time, so a multi-stop route is built leg by
/// leg and concatenated. If a leg has no routable path — across water, say — that
/// leg falls back to a straight line so playback still works.
@MainActor
final class RouteService: ObservableObject {
    @Published private(set) var isRouting = false

    struct Result {
        var coordinates: [CLLocationCoordinate2D]
        /// True when at least one leg could not be snapped to a real path.
        var hasStraightLegs: Bool

        var polyline: MKPolyline {
            MKPolyline(coordinates: coordinates, count: coordinates.count)
        }
    }

    func buildRoute(
        through waypoints: [CLLocationCoordinate2D], walking: Bool
    ) async -> Result {
        guard waypoints.count >= 2 else {
            return Result(coordinates: waypoints, hasStraightLegs: false)
        }

        isRouting = true
        defer { isRouting = false }

        var coordinates: [CLLocationCoordinate2D] = []
        var hasStraightLegs = false

        for (start, end) in zip(waypoints, waypoints.dropFirst()) {
            let leg = await routeLeg(from: start, to: end, walking: walking)

            if let leg {
                // Drop the duplicated join between consecutive legs.
                coordinates.append(contentsOf: coordinates.isEmpty ? leg : Array(leg.dropFirst()))
            } else {
                hasStraightLegs = true
                if coordinates.isEmpty { coordinates.append(start) }
                coordinates.append(end)
            }
        }

        return Result(coordinates: coordinates, hasStraightLegs: hasStraightLegs)
    }

    private func routeLeg(
        from start: CLLocationCoordinate2D,
        to end: CLLocationCoordinate2D,
        walking: Bool
    ) async -> [CLLocationCoordinate2D]? {
        let request = MKDirections.Request()
        request.source = MKMapItem(placemark: MKPlacemark(coordinate: start))
        request.destination = MKMapItem(placemark: MKPlacemark(coordinate: end))
        request.transportType = walking ? .walking : .automobile

        guard
            let response = try? await MKDirections(request: request).calculate(),
            let route = response.routes.first
        else { return nil }

        return route.polyline.coordinates
    }
}

extension MKPolyline {
    /// The polyline's points as coordinates.
    var coordinates: [CLLocationCoordinate2D] {
        var result = [CLLocationCoordinate2D](
            repeating: kCLLocationCoordinate2DInvalid, count: pointCount
        )
        getCoordinates(&result, range: NSRange(location: 0, length: pointCount))
        return result
    }
}
