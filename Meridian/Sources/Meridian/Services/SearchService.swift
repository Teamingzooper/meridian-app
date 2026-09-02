import Foundation
import MapKit

/// Address and place-name search, backed by the same index Apple Maps uses.
///
/// Free, keyless and built into macOS — the reason a native app beats a browser
/// build here, where search would otherwise mean paying a maps provider.
@MainActor
final class SearchService: ObservableObject {
    @Published private(set) var results: [MKMapItem] = []
    @Published private(set) var isSearching = false

    private var task: Task<Void, Never>?

    /// Debounced so typing does not fire a request per keystroke.
    func search(_ query: String, near region: MKCoordinateRegion?) {
        task?.cancel()

        let trimmed = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard trimmed.count >= 2 else {
            results = []
            isSearching = false
            return
        }

        task = Task { [weak self] in
            try? await Task.sleep(for: .milliseconds(280))
            guard !Task.isCancelled, let self else { return }

            self.isSearching = true
            defer { self.isSearching = false }

            let request = MKLocalSearch.Request()
            request.naturalLanguageQuery = trimmed
            if let region { request.region = region }

            let response = try? await MKLocalSearch(request: request).start()
            guard !Task.isCancelled else { return }
            self.results = response?.mapItems ?? []
        }
    }

    func clear() {
        task?.cancel()
        results = []
        isSearching = false
    }
}

extension MKMapItem {
    /// A short label for a search result, falling back through what MapKit gives us.
    var displayName: String {
        if let name, !name.isEmpty { return name }
        if let locality = placemark.locality { return locality }
        return "Dropped pin"
    }

    /// The line under the name: street, city, country as available.
    var displayDetail: String {
        let parts = [
            placemark.thoroughfare,
            placemark.locality,
            placemark.administrativeArea,
            placemark.country,
        ].compactMap { $0 }
        return parts.joined(separator: ", ")
    }
}
