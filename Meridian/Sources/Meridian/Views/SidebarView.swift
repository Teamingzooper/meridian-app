import SwiftUI

/// Everything except the map, in one scrolling column.
///
/// Replaces the nested Saved/Route then Bookmarks/Recent pickers: two rows of
/// segmented controls hid three quarters of the content behind a mode switch and
/// still left the column mostly empty. Collapsible sections show all of it at once.
struct SidebarView: View {
    @EnvironmentObject private var model: AppModel

    @State private var filter = ""
    @State private var showBookmarks = true
    @State private var showRecent = true
    @State private var showRoute = true

    var body: some View {
        VStack(spacing: 0) {
            StatusHeader()
            filterField
            Divider()

            ScrollView {
                LazyVStack(alignment: .leading, spacing: 0) {
                    currentSection
                    bookmarksSection
                    recentSection
                    routeSection
                }
                .padding(.bottom, 10)
            }

            Divider()
            SidebarFooter()
        }
    }

    // MARK: - Filter

    private var filterField: some View {
        HStack(spacing: 5) {
            Image(systemName: "line.3.horizontal.decrease")
                .font(.system(size: 10))
                .foregroundStyle(.secondary)

            TextField("Filter places", text: $filter)
                .textFieldStyle(.plain)
                .font(.system(size: 11))

            if !filter.isEmpty {
                Button { filter = "" } label: {
                    Image(systemName: "xmark.circle.fill").font(.system(size: 10))
                }
                .buttonStyle(.borderless)
                .foregroundStyle(.secondary)
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 7)
    }

    private func matching(_ places: [Place]) -> [Place] {
        guard !filter.isEmpty else { return places }
        return places.filter { $0.name.localizedCaseInsensitiveContains(filter) }
    }

    // MARK: - Current

    /// What the phone is doing right now, and the one action that changes it.
    private var currentSection: some View {
        VStack(alignment: .leading, spacing: 6) {
            SectionLabel(title: "CURRENT")

            if let simulated = model.simulatedCoordinate {
                HStack(spacing: 6) {
                    Circle().fill(.blue).frame(width: 7, height: 7)
                    VStack(alignment: .leading, spacing: 1) {
                        Text(model.lastApplied?.name ?? "Simulated location")
                            .font(.system(size: 12, weight: .medium))
                            .lineLimit(1)
                        Text(String(format: "%.5f, %.5f", simulated.latitude, simulated.longitude))
                            .font(.system(size: 9, design: .monospaced))
                            .foregroundStyle(.secondary)
                            .textSelection(.enabled)
                    }
                    Spacer()
                }
            } else if let last = model.lastApplied {
                Button {
                    model.setSimulating(true)
                } label: {
                    Label("Switch on for \(last.name)", systemImage: "location.fill")
                        .font(.system(size: 11))
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                .buttonStyle(.bordered)
                .controlSize(.small)
            } else {
                HStack(spacing: 6) {
                    Circle().fill(.green).frame(width: 7, height: 7)
                    Text("Using the phone's real GPS")
                        .font(.system(size: 11))
                        .foregroundStyle(.secondary)
                }
            }
        }
        .padding(.horizontal, 12)
        .padding(.top, 8)
        .padding(.bottom, 10)
    }

    // MARK: - Places

    private var bookmarksSection: some View {
        let places = matching(model.store.bookmarks)
        return CollapsibleSection(
            title: "BOOKMARKS", count: model.store.bookmarks.count, isExpanded: $showBookmarks
        ) {
            if places.isEmpty {
                EmptyHint(model.store.bookmarks.isEmpty
                          ? "Star a place on the map to save it."
                          : "Nothing matches that filter.")
            } else {
                ForEach(places) { place in
                    PlaceRow(place: place, isBookmark: true)
                }
            }
        }
    }

    private var recentSection: some View {
        let places = matching(model.store.history)
        return CollapsibleSection(
            title: "RECENT", count: model.store.history.count, isExpanded: $showRecent
        ) {
            if places.isEmpty {
                EmptyHint(model.store.history.isEmpty
                          ? "Places you set will appear here."
                          : "Nothing matches that filter.")
            } else {
                ForEach(places.prefix(12)) { place in
                    PlaceRow(place: place, isBookmark: false)
                }
                if places.count > 12 {
                    EmptyHint("\(places.count - 12) more…")
                }
            }
        }
    }

    // MARK: - Route

    private var routeSection: some View {
        CollapsibleSection(
            title: "ROUTE", count: model.waypoints.count, isExpanded: $showRoute
        ) {
            if model.waypoints.isEmpty {
                EmptyHint("Right-click the map and choose Add as Waypoint.")
            } else {
                ForEach(Array(model.waypoints.enumerated()), id: \.element.id) { index, place in
                    WaypointRow(index: index, place: place)
                }
            }
            RouteControls()
        }
    }
}

// MARK: - Building blocks

private struct SectionLabel: View {
    let title: String

    var body: some View {
        Text(title)
            .font(.system(size: 9, weight: .semibold))
            .foregroundStyle(.tertiary)
    }
}

private struct EmptyHint: View {
    let text: String
    init(_ text: String) { self.text = text }

    var body: some View {
        Text(text)
            .font(.system(size: 10))
            .foregroundStyle(.secondary)
            .fixedSize(horizontal: false, vertical: true)
            .padding(.horizontal, 12)
            .padding(.vertical, 5)
    }
}

/// A section header that folds its contents away, with a count so a collapsed
/// section still tells you what is in it.
private struct CollapsibleSection<Content: View>: View {
    let title: String
    let count: Int
    @Binding var isExpanded: Bool
    @ViewBuilder var content: () -> Content

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Divider().padding(.bottom, 6)

            Button {
                withAnimation(.easeInOut(duration: 0.16)) { isExpanded.toggle() }
            } label: {
                HStack(spacing: 5) {
                    Image(systemName: "chevron.right")
                        .font(.system(size: 8, weight: .bold))
                        .rotationEffect(.degrees(isExpanded ? 90 : 0))
                        .foregroundStyle(.tertiary)
                    SectionLabel(title: title)
                    if count > 0 {
                        Text("\(count)")
                            .font(.system(size: 9, weight: .medium))
                            .foregroundStyle(.tertiary)
                            .padding(.horizontal, 4)
                            .padding(.vertical, 1)
                            .background(.quaternary, in: Capsule())
                    }
                    Spacer()
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 3)
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)

            if isExpanded {
                content()
                    .padding(.top, 3)
            }
        }
        .padding(.bottom, 6)
    }
}
