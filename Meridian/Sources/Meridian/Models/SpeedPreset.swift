import Foundation

/// Travel speeds offered for route playback.
enum SpeedPreset: String, CaseIterable, Identifiable {
    case walk, bike, drive

    var id: String { rawValue }

    /// Metres per second, matching the sidecar's presets.
    var metresPerSecond: Double {
        switch self {
        case .walk: return 1.4
        case .bike: return 4.2
        case .drive: return 13.4
        }
    }

    var label: String {
        switch self {
        case .walk: return "Walk"
        case .bike: return "Bike"
        case .drive: return "Drive"
        }
    }

    var symbol: String {
        switch self {
        case .walk: return "figure.walk"
        case .bike: return "bicycle"
        case .drive: return "car.fill"
        }
    }

    /// The MapKit transport type used to snap waypoints to real paths.
    var isWalking: Bool { self != .drive }
}
