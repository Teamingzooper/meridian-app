import Foundation

/// Talks to `meridiand` over loopback.
///
/// The token is read from disk on each request rather than cached, so restarting
/// the helper — which mints a fresh token — does not require restarting the app.
actor DaemonClient {
    private let baseURL: URL
    private let tokenURL: URL
    private let session: URLSession

    init(port: Int = 8787) {
        self.baseURL = URL(string: "http://127.0.0.1:\(port)")!
        self.tokenURL = FileManager.default
            .homeDirectoryForCurrentUser
            .appending(path: "Library/Application Support/Meridian/token")

        let config = URLSessionConfiguration.ephemeral
        config.timeoutIntervalForRequest = 20
        // Opening a channel can mean mounting a developer disk image, which is
        // slow the first time a device is seen.
        config.timeoutIntervalForResource = 200
        self.session = URLSession(configuration: config)
    }

    private func token() throws -> String {
        guard let raw = try? String(contentsOf: tokenURL, encoding: .utf8) else {
            throw ClientError.noToken
        }
        return raw.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    /// True when the helper answers, regardless of whether a phone is attached.
    func isAlive() async -> Bool {
        var request = URLRequest(url: baseURL.appending(path: "health"))
        request.timeoutInterval = 2
        guard let (_, response) = try? await session.data(for: request) else { return false }
        return (response as? HTTPURLResponse)?.statusCode == 200
    }

    @discardableResult
    func send(_ path: String, body: [String: Any]? = nil) async throws -> DaemonStatus {
        try await send(path, body: body, as: DaemonStatus.self)
    }

    /// Endpoints that answer with something other than a status, such as GPX.
    func send<T: Decodable>(
        _ path: String, body: [String: Any]? = nil, as type: T.Type
    ) async throws -> T {
        var request = URLRequest(url: baseURL.appending(path: path))
        request.httpMethod = body == nil && path == "status" ? "GET" : "POST"
        request.setValue("Bearer \(try token())", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        if request.httpMethod == "POST" {
            request.httpBody = try JSONSerialization.data(withJSONObject: body ?? [:])
        }

        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw ClientError.notRunning
        }

        let code = (response as? HTTPURLResponse)?.statusCode ?? 0

        // The sidecar reports device trouble as 409 with actionable guidance.
        if code == 409 || code == 400 || code == 504 {
            if let wrapper = try? JSONDecoder().decode(ErrorEnvelope.self, from: data) {
                throw wrapper.error
            }
        }
        guard code == 200 else { throw ClientError.badResponse(code) }

        do {
            return try JSONDecoder().decode(T.self, from: data)
        } catch {
            throw ClientError.decoding(error.localizedDescription)
        }
    }

    private struct ErrorEnvelope: Decodable {
        let error: DaemonError
    }

    // MARK: - Commands

    func status() async throws -> DaemonStatus { try await send("status") }

    func devices() async throws -> [DaemonStatus.Device] {
        try await send("devices", as: DaemonStatus.DeviceList.self).devices
    }

    func select(udid: String, kind: String) async throws -> DaemonStatus {
        try await send("select", body: ["udid": udid, "kind": kind])
    }
    func connect() async throws -> DaemonStatus { try await send("connect", body: [:]) }
    func clear() async throws -> DaemonStatus { try await send("clear", body: [:]) }
    func pause() async throws -> DaemonStatus { try await send("pause", body: [:]) }
    func resume() async throws -> DaemonStatus { try await send("resume", body: [:]) }
    func stop() async throws -> DaemonStatus { try await send("stop", body: [:]) }

    func setLocation(latitude: Double, longitude: Double) async throws -> DaemonStatus {
        try await send("location", body: ["lat": latitude, "lon": longitude])
    }

    func setJitter(radiusMetres: Double) async throws -> DaemonStatus {
        try await send("jitter", body: ["radiusM": radiusMetres])
    }

    func playRoute(
        coordinates: [[Double]], speedMps: Double, loop: Bool
    ) async throws -> DaemonStatus {
        try await send("route", body: [
            "coords": coordinates,
            "speedMps": speedMps,
            "loop": loop,
        ])
    }

    // MARK: - GPX
    //
    // Parsed by the sidecar rather than here so there is one GPX implementation,
    // and it is the one with tests behind it.

    struct ParsedGPX: Decodable {
        var name: String
        var coords: [[Double]]
        var count: Int
    }

    private struct WrittenGPX: Decodable {
        var gpx: String
    }

    func parseGPX(_ document: String) async throws -> ParsedGPX {
        try await send("gpx/parse", body: ["gpx": document], as: ParsedGPX.self)
    }

    func writeGPX(coordinates: [[Double]], name: String) async throws -> String {
        try await send(
            "gpx/write", body: ["coords": coordinates, "name": name], as: WrittenGPX.self
        ).gpx
    }
}
