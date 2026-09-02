import MapKit
import SwiftUI

/// Search, pick a point, send the phone there.
struct MapPane: View {
    @EnvironmentObject private var model: AppModel
    @State private var query = ""
    @State private var camera: MapCameraPosition = .automatic
    @State private var visibleRegion: MKCoordinateRegion?
    /// A point dropped from the map's context menu, awaiting confirmation.
    @State private var pendingPin: Place?
    /// Cursor position in map-local coordinates, captured for the context menu.
    @State private var hoverPoint: CGPoint?

    var body: some View {
        VStack(spacing: 0) {
            searchField

            ZStack(alignment: .top) {
                map
                if !model.search.results.isEmpty {
                    resultsList
                }
            }

            actionBar
            legend
        }
    }

    // MARK: - Search

    private var searchField: some View {
        HStack(spacing: 6) {
            Image(systemName: "magnifyingglass")
                .foregroundStyle(.secondary)
                .font(.system(size: 11))

            TextField("Search for a place or address", text: $query)
                .textFieldStyle(.plain)
                .font(.system(size: 12))
                .onChange(of: query) { model.search.search(query, near: visibleRegion) }

            if model.search.isSearching {
                ProgressView().controlSize(.mini)
            } else if !query.isEmpty {
                Button {
                    query = ""
                    model.search.clear()
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundStyle(.secondary)
                }
                .buttonStyle(.borderless)
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 8)
    }

    private var resultsList: some View {
        ScrollView {
            VStack(spacing: 0) {
                ForEach(model.search.results, id: \.self) { item in
                    Button {
                        choose(item)
                    } label: {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(item.displayName)
                                .font(.system(size: 12, weight: .medium))
                            if !item.displayDetail.isEmpty {
                                Text(item.displayDetail)
                                    .font(.system(size: 10))
                                    .foregroundStyle(.secondary)
                            }
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 7)
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    Divider()
                }
            }
        }
        .frame(maxHeight: 210)
        .background(.regularMaterial)
    }

    private func choose(_ item: MKMapItem) {
        let place = Place(name: item.displayName, coordinate: item.placemark.coordinate)
        model.selection = place
        pendingPin = nil
        camera = .region(MKCoordinateRegion(
            center: place.coordinate,
            span: MKCoordinateSpan(latitudeDelta: 0.01, longitudeDelta: 0.01)
        ))
        query = ""
        model.search.clear()
    }

    // MARK: - Map

    private var map: some View {
        MapReader { proxy in
            Map(position: $camera) {
                // Green: where you actually are.
                if let real = model.location.coordinate {
                    Annotation("You are here", coordinate: real) {
                        RealLocationDot()
                    }
                    .annotationTitles(.hidden)
                }

                // Blue: where the phone is reporting from right now.
                if let simulated = model.simulatedCoordinate {
                    Marker("Simulated", coordinate: simulated)
                        .tint(.blue)
                }

                // Orange: chosen but not sent to the phone yet — a search result or
                // a right-clicked point. Hidden once it is the applied location, so
                // one place never shows two pins.
                if let selection = model.selection, !selectionIsApplied {
                    Marker(selection.name, coordinate: selection.coordinate)
                        .tint(.orange)
                }

                if let preview = model.routePreview {
                    MapPolyline(coordinates: preview.coordinates)
                        .stroke(.blue, lineWidth: 4)
                }
            }
            // Track the cursor so the context menu knows which point was clicked.
            .onContinuousHover { phase in
                if case .active(let location) = phase { hoverPoint = location }
            }
            // Right-click rather than a tap gesture: single-click pans the map and
            // double-click is MapKit's own zoom, so neither is ours to take.
            .contextMenu {
                Button("Set Location Here…") { placePin(using: proxy) }
                Button("Add as Waypoint") { addWaypoint(using: proxy) }
            }
            .onMapCameraChange { context in
                visibleRegion = context.region
            }
            .overlay(alignment: .bottom) {
                if let pending = pendingPin {
                    confirmBar(for: pending)
                        .padding(10)
                        .transition(.move(edge: .bottom).combined(with: .opacity))
                }
            }
            .animation(.easeInOut(duration: 0.16), value: pendingPin)
        }
    }

    /// True when the selected pin is the place the phone is already reporting.
    private var selectionIsApplied: Bool {
        guard let selection = model.selection,
              let simulated = model.simulatedCoordinate else { return false }
        return selection.isEffectivelySame(as: simulated)
    }

    /// The coordinate under the cursor when the context menu was opened.
    ///
    /// Falls back to the centre of the visible map if hover tracking gave us
    /// nothing, so the menu item always does something rather than failing quietly.
    private func hoveredPlace(using proxy: MapProxy) -> Place? {
        if let point = hoverPoint, let coordinate = proxy.convert(point, from: .local) {
            return Place(name: "Dropped pin", coordinate: coordinate)
        }
        if let centre = visibleRegion?.center {
            return Place(name: "Map centre", coordinate: centre)
        }
        return nil
    }

    private func placePin(using proxy: MapProxy) {
        guard let place = hoveredPlace(using: proxy) else { return }
        pendingPin = place
        model.selection = place
    }

    private func addWaypoint(using proxy: MapProxy) {
        guard let place = hoveredPlace(using: proxy) else { return }
        model.selection = place
        model.addWaypoint(place)
    }

    /// Confirmation for a placed point, so nothing moves the phone without a second step.
    private func confirmBar(for pending: Place) -> some View {
        HStack(spacing: 8) {
            Image(systemName: "mappin.circle.fill")
                .foregroundStyle(.orange)

            VStack(alignment: .leading, spacing: 1) {
                Text("Set location here?")
                    .font(.system(size: 12, weight: .medium))
                Text(pending.prettyCoordinates)
                    .font(.system(size: 9, design: .monospaced))
                    .foregroundStyle(.secondary)
            }

            Spacer(minLength: 6)

            Button("Cancel") {
                pendingPin = nil
                model.selection = nil
            }
            .buttonStyle(.bordered)
            .controlSize(.small)

            Button("Confirm") {
                model.apply(pending)
                pendingPin = nil
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.small)
            .keyboardShortcut(.defaultAction)
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 8)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 9))
        .shadow(radius: 5, y: 2)
    }

    // MARK: - Actions

    private var actionBar: some View {
        HStack(spacing: 8) {
            Button {
                if let selection = model.selection { model.apply(selection) }
            } label: {
                Label("Set Location", systemImage: "location.fill")
                    .font(.system(size: 12, weight: .medium))
            }
            .buttonStyle(.borderedProminent)
            .disabled(model.selection == nil)

            Button {
                if let selection = model.selection { model.store.addBookmark(selection) }
            } label: {
                Image(systemName: isBookmarked ? "star.fill" : "star")
            }
            .buttonStyle(.bordered)
            .disabled(model.selection == nil)
            .help("Save this place")

            Button {
                if let selection = model.selection { model.addWaypoint(selection) }
            } label: {
                Image(systemName: "point.topleft.down.to.point.bottomright.curvepath")
            }
            .buttonStyle(.bordered)
            .disabled(model.selection == nil)
            .help("Add as a route waypoint")

            Spacer()

            if let selection = model.selection {
                Text(selection.prettyCoordinates)
                    .font(.system(size: 10, design: .monospaced))
                    .foregroundStyle(.secondary)
                    .textSelection(.enabled)
            }
        }
        .padding(.horizontal, 14)
        .padding(.top, 9)
        .padding(.bottom, 2)
    }

    /// Says what the colours mean, so the map needs no explaining.
    private var legend: some View {
        HStack(spacing: 12) {
            if model.location.isDenied {
                Label("Location access off — no green dot", systemImage: "location.slash")
                    .font(.system(size: 9))
                    .foregroundStyle(.secondary)
            } else {
                key(color: .green, label: "You")
            }

            if model.simulatedCoordinate != nil {
                key(color: .blue, label: "Phone")
            }
            if model.selection != nil, !selectionIsApplied {
                key(color: .orange, label: "Selected")
            }
            Spacer()
        }
        .padding(.horizontal, 14)
        .padding(.bottom, 8)
    }

    private func key(color: Color, label: String) -> some View {
        HStack(spacing: 4) {
            Circle().fill(color).frame(width: 7, height: 7)
            Text(label)
                .font(.system(size: 9))
                .foregroundStyle(.secondary)
        }
    }

    private var isBookmarked: Bool {
        guard let selection = model.selection else { return false }
        return model.store.isBookmarked(selection.coordinate)
    }
}
