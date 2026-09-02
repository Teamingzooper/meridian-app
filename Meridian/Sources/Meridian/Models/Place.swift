import CoreLocation
import Foundation

/// A saved or recently-used location.
struct Place: Identifiable, Codable, Equatable {
    var id: UUID = UUID()
    var name: String
    var latitude: Double
    var longitude: Double
    var savedAt: Date = Date()

    var coordinate: CLLocationCoordinate2D {
        CLLocationCoordinate2D(latitude: latitude, longitude: longitude)
    }

    /// Rounded to roughly a metre — more precision than that is noise in a label.
    var prettyCoordinates: String {
        String(format: "%.5f, %.5f", latitude, longitude)
    }

    init(name: String, coordinate: CLLocationCoordinate2D) {
        self.name = name
        self.latitude = coordinate.latitude
        self.longitude = coordinate.longitude
    }
}
