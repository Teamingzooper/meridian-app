import Foundation
import SwiftUI

/// Saved routes, persisted as JSON beside bookmarks and history.
///
/// Kept separate from `PlaceStore` so each store owns one file and one concept.
@MainActor
final class RouteStore: ObservableObject {
    @Published private(set) var routes: [SavedRoute] = []

    private let directory: URL
    private var routesURL: URL { directory.appending(path: "routes.json") }

    init(directory: URL? = nil) {
        self.directory = directory ?? FileManager.default
            .homeDirectoryForCurrentUser
            .appending(path: "Library/Application Support/Meridian")
        try? FileManager.default.createDirectory(
            at: self.directory, withIntermediateDirectories: true
        )
        routes = load()
    }

    func save(_ route: SavedRoute) {
        // Saving under an existing name replaces it, which is what "Save" means
        // to someone who just edited a route they already had.
        routes.removeAll { $0.name.caseInsensitiveCompare(route.name) == .orderedSame }
        routes.insert(route, at: 0)
        persist()
    }

    func remove(_ route: SavedRoute) {
        routes.removeAll { $0.id == route.id }
        persist()
    }

    func rename(_ route: SavedRoute, to name: String) {
        let trimmed = name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty,
              let index = routes.firstIndex(where: { $0.id == route.id }) else { return }
        routes[index].name = trimmed
        persist()
    }

    func contains(name: String) -> Bool {
        routes.contains { $0.name.caseInsensitiveCompare(name) == .orderedSame }
    }

    // MARK: - Disk

    private func load() -> [SavedRoute] {
        guard let data = try? Data(contentsOf: routesURL) else { return [] }
        return (try? JSONDecoder().decode([SavedRoute].self, from: data)) ?? []
    }

    private func persist() {
        guard let data = try? JSONEncoder().encode(routes) else { return }
        try? data.write(to: routesURL, options: .atomic)
    }
}
