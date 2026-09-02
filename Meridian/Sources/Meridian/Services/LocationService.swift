import CoreLocation
import SwiftUI

/// The Mac's own location, shown so you can see where you actually are next to
/// where the phone claims to be.
///
/// The DVT channel only writes location — it cannot read the phone's real fix —
/// but the Mac is on the other end of the same USB cable, so its position is the
/// same place to within a room.
@MainActor
final class LocationService: NSObject, ObservableObject {
    @Published private(set) var coordinate: CLLocationCoordinate2D?
    @Published private(set) var authorization: CLAuthorizationStatus = .notDetermined

    private let manager = CLLocationManager()

    /// True once the user has answered the prompt with a no.
    var isDenied: Bool {
        authorization == .denied || authorization == .restricted
    }

    override init() {
        super.init()
        manager.delegate = self
        // A green "you are here" dot does not need metre accuracy, and asking for
        // less keeps the radio quiet.
        manager.desiredAccuracy = kCLLocationAccuracyHundredMeters
        manager.distanceFilter = 25
    }

    func start() {
        authorization = manager.authorizationStatus
        if authorization == .notDetermined {
            manager.requestWhenInUseAuthorization()
        } else if !isDenied {
            manager.startUpdatingLocation()
        }
    }

    func stop() {
        manager.stopUpdatingLocation()
    }
}

extension LocationService: CLLocationManagerDelegate {
    nonisolated func locationManager(
        _ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]
    ) {
        guard let latest = locations.last else { return }
        let coordinate = latest.coordinate
        Task { @MainActor [weak self] in
            self?.coordinate = coordinate
        }
    }

    nonisolated func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        let status = manager.authorizationStatus
        Task { @MainActor [weak self] in
            guard let self else { return }
            self.authorization = status
            switch status {
            case .authorized, .authorizedAlways:
                manager.startUpdatingLocation()
            default:
                self.coordinate = nil
            }
        }
    }

    nonisolated func locationManager(
        _ manager: CLLocationManager, didFailWithError error: Error
    ) {
        // A transient failure just means no dot this cycle; nothing to escalate.
        Task { @MainActor [weak self] in self?.coordinate = nil }
    }
}
