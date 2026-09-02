import SwiftUI

/// Bookmarks and recent locations, one tap from being applied.
struct SavedPane: View {
    @EnvironmentObject private var model: AppModel
    /// Called after applying, for layouts that need to reveal the map afterwards.
    var onApply: () -> Void = {}

    @State private var section: Section = .bookmarks
    @State private var renaming: Place?
    @State private var draftName = ""

    enum Section: String, CaseIterable, Identifiable {
        case bookmarks = "Bookmarks"
        case history = "Recent"
        var id: String { rawValue }
    }

    private var places: [Place] {
        section == .bookmarks ? model.store.bookmarks : model.store.history
    }

    var body: some View {
        VStack(spacing: 0) {
            Picker("", selection: $section) {
                ForEach(Section.allCases) { Text($0.rawValue).tag($0) }
            }
            .pickerStyle(.segmented)
            .labelsHidden()
            .padding(.horizontal, 12)
            .padding(.vertical, 7)

            if places.isEmpty {
                emptyState
            } else {
                list
            }
        }
        .sheet(item: $renaming) { place in
            renameSheet(for: place)
        }
    }

    private var emptyState: some View {
        VStack(spacing: 6) {
            Spacer()
            Image(systemName: section == .bookmarks ? "star" : "clock")
                .font(.system(size: 26))
                .foregroundStyle(.tertiary)
            Text(section == .bookmarks ? "No bookmarks yet" : "No recent places")
                .font(.system(size: 12, weight: .medium))
            Text(section == .bookmarks
                 ? "Star a place on the Map tab to keep it here."
                 : "Places you set will show up here.")
                .font(.system(size: 11))
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 40)
            Spacer()
        }
    }

    private var list: some View {
        List {
            ForEach(places) { place in
                row(place)
            }
            .onMove { source, destination in
                guard section == .bookmarks else { return }
                model.store.moveBookmarks(from: source, to: destination)
            }
        }
        .listStyle(.plain)
    }

    private func row(_ place: Place) -> some View {
        HStack(spacing: 8) {
            VStack(alignment: .leading, spacing: 1) {
                Text(place.name)
                    .font(.system(size: 12))
                    .lineLimit(1)
                Text(place.prettyCoordinates)
                    .font(.system(size: 9, design: .monospaced))
                    .foregroundStyle(.secondary)
            }

            Spacer()

            Button {
                model.apply(place)
                onApply()
            } label: {
                Image(systemName: "location.fill")
                    .font(.system(size: 10))
            }
            .buttonStyle(.borderless)
            .help("Send the phone here")
        }
        .listRowInsets(EdgeInsets(top: 3, leading: 10, bottom: 3, trailing: 8))
        .contentShape(Rectangle())
        .contextMenu {
            Button("Add as Waypoint") { model.addWaypoint(place) }
            if section == .bookmarks {
                Button("Rename…") {
                    draftName = place.name
                    renaming = place
                }
                Button("Remove", role: .destructive) { model.store.removeBookmark(place) }
            } else {
                Button("Save as Bookmark") { model.store.addBookmark(place) }
                Button("Clear History", role: .destructive) { model.store.clearHistory() }
            }
        }
    }

    private func renameSheet(for place: Place) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Rename bookmark")
                .font(.system(size: 13, weight: .semibold))

            TextField("Name", text: $draftName)
                .textFieldStyle(.roundedBorder)
                .frame(width: 240)

            HStack {
                Spacer()
                Button("Cancel") { renaming = nil }
                Button("Save") {
                    model.store.renameBookmark(place, to: draftName)
                    renaming = nil
                }
                .keyboardShortcut(.defaultAction)
            }
        }
        .padding(16)
    }
}
