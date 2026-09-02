import Foundation

/// The sidecar's view of the world, as returned by every command.
struct DaemonStatus: Decodable, Equatable {
    var connected: Bool
    var mode: Mode
    var device: Device?
    var location: Location?
    var route: RouteStatus?
    var jitterM: Double
    var error: DaemonError?

    enum Mode: String, Decodable {
        case idle, fixed, route
    }

    struct Device: Decodable, Equatable {
        var udid: String
        var name: String
        var iosVersion: String
        var transport: String
    }

    struct Location: Decodable, Equatable {
        var lat: Double
        var lon: Double
    }

    struct RouteStatus: Decodable, Equatable {
        var progress: Double
        var paused: Bool
        var loop: Bool
        var speedMps: Double
        var lengthM: Double
        var durationS: Double
        var remainingS: Double
    }

    /// Placeholder shown before the first successful poll.
    static let unknown = DaemonStatus(
        connected: false, mode: .idle, device: nil, location: nil,
        route: nil, jitterM: 0, error: nil
    )
}

/// A device-side failure paired with the action that resolves it.
struct DaemonError: Decodable, Equatable, Error {
    var code: String
    var message: String
    var recoverable: Bool

    /// Failures the user resolves on the phone, not by retrying.
    var needsUserAction: Bool { !recoverable }
}

/// Failures that never reached the sidecar.
enum ClientError: LocalizedError {
    case notRunning
    case noToken
    case badResponse(Int)
    case decoding(String)

    var errorDescription: String? {
        switch self {
        case .notRunning:
            return "Meridian's helper isn't running."
        case .noToken:
            return "Couldn't read Meridian's access token."
        case .badResponse(let code):
            return "The helper returned an unexpected response (\(code))."
        case .decoding(let detail):
            return "Couldn't read the helper's reply: \(detail)"
        }
    }
}
