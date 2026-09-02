import CoreLocation
import Foundation

/// A named route, with the settings it was built for.
///
/// Only the waypoints are stored, not the road-snapped polyline: the snapped
/// path depends on the travel mode and on map data that changes, so it is
/// rebuilt on load rather than preserved stale.
struct SavedRoute: Identifiable, Codable, Equatable {
    var id: UUID = UUID()
    var name: String
    var waypoints: [Place]
    var speed: SpeedPreset
    var loop: Bool
    var savedAt: Date = Date()

    var summary: String {
        let stops = waypoints.count == 1 ? "1 stop" : "\(waypoints.count) stops"
        return "\(stops) · \(speed.label.lowercased())\(loop ? " · loop" : "")"
    }

    init(name: String, waypoints: [Place], speed: SpeedPreset, loop: Bool) {
        self.name = name
        self.waypoints = waypoints
        self.speed = speed
        self.loop = loop
    }
}

// Persisted by name, so reordering the enum cannot silently change saved routes.
extension SpeedPreset: Codable {}
