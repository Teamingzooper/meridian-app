import CoreLocation
import SwiftUI
import Foundation

/// Bookmarks and history, persisted as plain JSON.
///
/// Writes are atomic and failures are non-fatal: losing a bookmark is a far
/// smaller problem than refusing to set a location because a disk write failed.
@MainActor
final class PlaceStore: ObservableObject {
    @Published private(set) var bookmarks: [Place] = []
    @Published private(set) var history: [Place] = []

    /// Enough history to be useful, short enough to stay scannable.
    private let historyLimit = 40

    private let directory: URL
    private var bookmarksURL: URL { directory.appending(path: "bookmarks.json") }
    private var historyURL: URL { directory.appending(path: "history.json") }

    init(directory: URL? = nil) {
        self.directory = directory ?? FileManager.default
            .homeDirectoryForCurrentUser
            .appending(path: "Library/Application Support/Meridian")
        try? FileManager.default.createDirectory(at: self.directory, withIntermediateDirectories: true)
        bookmarks = load(bookmarksURL)
        history = load(historyURL)
    }

    // MARK: - Bookmarks

    func addBookmark(_ place: Place) {
        bookmarks.removeAll { $0.isEffectivelySamePlace(as: place) }
        bookmarks.insert(place, at: 0)
        save(bookmarks, to: bookmarksURL)
    }

    func removeBookmark(_ place: Place) {
        bookmarks.removeAll { $0.id == place.id }
        save(bookmarks, to: bookmarksURL)
    }

    func renameBookmark(_ place: Place, to name: String) {
        guard let index = bookmarks.firstIndex(where: { $0.id == place.id }) else { return }
        let trimmed = name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        bookmarks[index].name = trimmed
        save(bookmarks, to: bookmarksURL)
    }

    func moveBookmarks(from source: IndexSet, to destination: Int) {
        bookmarks.move(fromOffsets: source, toOffset: destination)
        save(bookmarks, to: bookmarksURL)
    }

    func isBookmarked(_ coordinate: CLLocationCoordinate2D) -> Bool {
        bookmarks.contains { $0.isEffectivelySame(as: coordinate) }
    }

    // MARK: - History

    func recordVisit(_ place: Place) {
        history.removeAll { $0.isEffectivelySamePlace(as: place) }
        history.insert(place, at: 0)
        if history.count > historyLimit {
            history = Array(history.prefix(historyLimit))
        }
        save(history, to: historyURL)
    }

    func clearHistory() {
        history = []
        save(history, to: historyURL)
    }

    // MARK: - Disk

    private func load(_ url: URL) -> [Place] {
        guard let data = try? Data(contentsOf: url) else { return [] }
        return (try? JSONDecoder().decode([Place].self, from: data)) ?? []
    }

    private func save(_ places: [Place], to url: URL) {
        guard let data = try? JSONEncoder().encode(places) else { return }
        try? data.write(to: url, options: .atomic)
    }
}

extension Place {
    /// Within about 10 metres, which is the same pin as far as a person is concerned.
    func isEffectivelySame(as coordinate: CLLocationCoordinate2D) -> Bool {
        abs(latitude - coordinate.latitude) < 0.0001
            && abs(longitude - coordinate.longitude) < 0.0001
    }

    func isEffectivelySamePlace(as other: Place) -> Bool {
        isEffectivelySame(as: other.coordinate)
    }
}
