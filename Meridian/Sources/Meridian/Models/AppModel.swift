import CoreLocation
import MapKit
import SwiftUI

/// Coordinates the sidecar, the stored places, and what the views show.
@MainActor
final class AppModel: ObservableObject {
    @Published var status: DaemonStatus = .unknown
    @Published var helperReachable = false

    /// The pin the user is currently pointing at, which may not be applied yet.
    @Published var selection: Place?

    /// The last place actually sent to the phone. Kept when simulation is switched
    /// off so the toggle has somewhere to return to.
    @Published private(set) var lastApplied: Place?

    @Published var waypoints: [Place] = []
    @Published var routePreview: RouteService.Result?
    @Published var speed: SpeedPreset = .walk
    @Published var loopRoute = false
    @Published var jitterEnabled = false

    @Published var banner: Banner?

    let store = PlaceStore()
    let search = SearchService()
    let routing = RouteService()

    private let client = DaemonClient()
    private let launcher = HelperLauncher()
    private var pollTask: Task<Void, Never>?

    struct Banner: Equatable {
        enum Kind { case error, notice, success }
        var kind: Kind
        var message: String
    }

    // MARK: - Lifecycle

    func start() {
        pollTask = Task { [weak self] in
            await self?.pollForever()
        }
    }

    func shutDown() {
        pollTask?.cancel()
        launcher.terminate()
    }

    /// Poll status so the UI reflects reality even when changed from elsewhere.
    private func pollForever() async {
        var launchAttempted = false

        while !Task.isCancelled {
            let alive = await client.isAlive()
            helperReachable = alive

            if alive {
                if let fresh = try? await client.status() { status = fresh }
            } else if !launchAttempted {
                launchAttempted = true
                if launcher.launch() {
                    // Give it a moment to bind its port before the next poll.
                    try? await Task.sleep(for: .seconds(2))
                } else {
                    banner = Banner(
                        kind: .error,
                        message: launcher.lastFailure
                            ?? "Meridian's helper isn't installed. Run scripts/setup.sh."
                    )
                }
                continue
            } else if !launcher.isLaunched {
                // It started and then died. Its log says why.
                banner = Banner(
                    kind: .error,
                    message: launcher.recentLog(lines: 3)
                        ?? "The helper stopped unexpectedly. See ~/Library/Logs/Meridian-helper.log"
                )
            }

            // Fast enough to feel live during playback, idle enough to be free.
            try? await Task.sleep(for: .milliseconds(status.mode == .route ? 500 : 1500))
        }
    }

    // MARK: - Actions

    private func perform(
        _ successMessage: String? = nil, _ work: @escaping () async throws -> DaemonStatus
    ) {
        Task { @MainActor in
            do {
                status = try await work()
                if let successMessage {
                    banner = Banner(kind: .success, message: successMessage)
                }
            } catch let error as DaemonError {
                banner = Banner(kind: error.needsUserAction ? .notice : .error, message: error.message)
            } catch {
                banner = Banner(kind: .error, message: error.localizedDescription)
            }
        }
    }

    /// True while the phone is reporting somewhere other than where it is.
    var isSimulating: Bool { status.mode != .idle }

    /// The toggle can be flipped on whenever there is somewhere to go back to.
    var canToggle: Bool { isSimulating || lastApplied != nil }

    func apply(_ place: Place) {
        selection = place
        lastApplied = place
        store.recordVisit(place)
        perform("Now at \(place.name)") { [client] in
            try await client.setLocation(latitude: place.latitude, longitude: place.longitude)
        }
    }

    /// Switch simulation on or off without forgetting where the phone was.
    func setSimulating(_ on: Bool) {
        if on {
            guard let place = lastApplied else { return }
            perform("Now at \(place.name)") { [client] in
                try await client.setLocation(latitude: place.latitude, longitude: place.longitude)
            }
        } else {
            // Deliberately keeps `lastApplied`, which is what the toggle restores.
            perform("Back to real GPS") { [client] in try await client.clear() }
        }
    }

    func clearLocation() {
        perform("Back to real GPS") { [client] in try await client.clear() }
    }

    func toggleJitter() {
        jitterEnabled.toggle()
        let radius = jitterEnabled ? 4.0 : 0.0
        perform { [client] in try await client.setJitter(radiusMetres: radius) }
    }

    // MARK: - Routes

    func addWaypoint(_ place: Place) {
        waypoints.append(place)
        Task { await refreshRoutePreview() }
    }

    func removeWaypoint(at offsets: IndexSet) {
        waypoints.remove(atOffsets: offsets)
        Task { await refreshRoutePreview() }
    }

    func clearWaypoints() {
        waypoints = []
        routePreview = nil
    }

    func refreshRoutePreview() async {
        guard waypoints.count >= 2 else {
            routePreview = nil
            return
        }
        let result = await routing.buildRoute(
            through: waypoints.map(\.coordinate), walking: speed.isWalking
        )
        routePreview = result
        if result.hasStraightLegs {
            banner = Banner(
                kind: .notice,
                message: "Part of this route has no road path, so it runs straight there."
            )
        }
    }

    func playRoute() {
        guard let preview = routePreview, preview.coordinates.count >= 2 else { return }
        if let first = waypoints.first { lastApplied = first }
        let coordinates = preview.coordinates.map { [$0.latitude, $0.longitude] }
        let speedMps = speed.metresPerSecond
        let loop = loopRoute

        perform("Route started") { [client] in
            try await client.playRoute(coordinates: coordinates, speedMps: speedMps, loop: loop)
        }
    }

    func pauseRoute() { perform { [client] in try await client.pause() } }
    func resumeRoute() { perform { [client] in try await client.resume() } }
    func stopRoute() { perform("Route stopped") { [client] in try await client.stop() } }
}
