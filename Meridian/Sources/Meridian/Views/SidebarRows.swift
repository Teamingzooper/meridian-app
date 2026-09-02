import SwiftUI

/// A saved or recent place. Actions appear on hover so the resting state stays
/// dense and readable, but everything is also in the context menu for discovery.
struct PlaceRow: View {
    @EnvironmentObject private var model: AppModel
    let place: Place
    let isBookmark: Bool

    @State private var isHovering = false
    @State private var isRenaming = false
    @State private var draftName = ""

    private var isCurrent: Bool {
        guard let simulated = model.simulatedCoordinate else { return false }
        return place.isEffectivelySame(as: simulated)
    }

    var body: some View {
        HStack(spacing: 7) {
            Circle()
                .fill(isCurrent ? Color.blue : Color.secondary.opacity(0.3))
                .frame(width: 6, height: 6)

            VStack(alignment: .leading, spacing: 1) {
                Text(place.name)
                    .font(.system(size: 12, weight: isCurrent ? .medium : .regular))
                    .lineLimit(1)
                Text(place.prettyCoordinates)
                    .font(.system(size: 9, design: .monospaced))
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }

            Spacer(minLength: 4)

            if isHovering {
                actions
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 4)
        .background(isHovering ? Color.secondary.opacity(0.1) : .clear)
        .contentShape(Rectangle())
        .onHover { isHovering = $0 }
        .onTapGesture { model.selection = place }
        .contextMenu { menu }
        .popover(isPresented: $isRenaming) { renameForm }
    }

    private var actions: some View {
        HStack(spacing: 2) {
            iconButton("point.topleft.down.to.point.bottomright.curvepath", "Add as waypoint") {
                model.addWaypoint(place)
            }
            iconButton(isBookmark ? "star.fill" : "star",
                       isBookmark ? "Remove bookmark" : "Save bookmark") {
                isBookmark ? model.store.removeBookmark(place) : model.store.addBookmark(place)
            }
            iconButton("location.fill", "Send the phone here") {
                model.apply(place)
            }
        }
    }

    private func iconButton(_ symbol: String, _ help: String, action: @escaping () -> Void)
        -> some View {
        Button(action: action) {
            Image(systemName: symbol)
                .font(.system(size: 10))
                .frame(width: 18, height: 16)
                .contentShape(Rectangle())
        }
        .buttonStyle(.borderless)
        .help(help)
    }

    @ViewBuilder
    private var menu: some View {
        Button("Set Location") { model.apply(place) }
        Button("Add as Waypoint") { model.addWaypoint(place) }
        Divider()
        if isBookmark {
            Button("Rename…") {
                draftName = place.name
                isRenaming = true
            }
            Button("Remove Bookmark", role: .destructive) { model.store.removeBookmark(place) }
        } else {
            Button("Save as Bookmark") { model.store.addBookmark(place) }
        }
    }

    private var renameForm: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Rename").font(.system(size: 12, weight: .semibold))
            TextField("Name", text: $draftName)
                .textFieldStyle(.roundedBorder)
                .frame(width: 200)
                .onSubmit { commitRename() }
            HStack {
                Spacer()
                Button("Cancel") { isRenaming = false }
                Button("Save") { commitRename() }
                    .keyboardShortcut(.defaultAction)
            }
        }
        .padding(14)
    }

    private func commitRename() {
        model.store.renameBookmark(place, to: draftName)
        isRenaming = false
    }
}

/// One stop on a route, numbered in travel order.
struct WaypointRow: View {
    @EnvironmentObject private var model: AppModel
    let index: Int
    let place: Place

    @State private var isHovering = false

    var body: some View {
        HStack(spacing: 7) {
            Text("\(index + 1)")
                .font(.system(size: 9, weight: .bold, design: .rounded))
                .foregroundStyle(.white)
                .frame(width: 15, height: 15)
                .background(Circle().fill(.blue))

            VStack(alignment: .leading, spacing: 1) {
                Text(place.name)
                    .font(.system(size: 12))
                    .lineLimit(1)
                Text(place.prettyCoordinates)
                    .font(.system(size: 9, design: .monospaced))
                    .foregroundStyle(.secondary)
            }

            Spacer(minLength: 4)

            if isHovering {
                Button {
                    model.removeWaypoint(at: IndexSet(integer: index))
                } label: {
                    Image(systemName: "minus.circle")
                        .font(.system(size: 11))
                }
                .buttonStyle(.borderless)
                .help("Remove this waypoint")
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 4)
        .background(isHovering ? Color.secondary.opacity(0.1) : .clear)
        .contentShape(Rectangle())
        .onHover { isHovering = $0 }
    }
}

/// Speed, looping, and the start/stop controls for a route.
struct RouteControls: View {
    @EnvironmentObject private var model: AppModel

    @State private var isNaming = false
    @State private var draftName = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 7) {
            Picker("", selection: $model.speed) {
                ForEach(SpeedPreset.allCases) { preset in
                    Label(preset.label, systemImage: preset.symbol).tag(preset)
                }
            }
            .pickerStyle(.segmented)
            .labelsHidden()
            .controlSize(.small)
            .onChange(of: model.speed) {
                // Walking and driving snap to different networks, so re-route.
                Task { await model.refreshRoutePreview() }
            }

            HStack(spacing: 6) {
                Toggle("Loop", isOn: $model.loopRoute)
                    .toggleStyle(.switch)
                    .controlSize(.mini)
                    .font(.system(size: 10))

                Spacer()

                if model.routing.isRouting {
                    ProgressView().controlSize(.mini)
                } else if let preview = model.routePreview {
                    Text(summary(for: preview))
                        .font(.system(size: 9))
                        .foregroundStyle(.secondary)
                }
            }

            if let route = model.status.route {
                playback(route)
            } else {
                HStack(spacing: 6) {
                    Button {
                        model.playRoute()
                    } label: {
                        Label("Start", systemImage: "play.fill")
                            .font(.system(size: 11))
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.small)
                    .disabled(model.routePreview == nil)

                    Button("Clear", action: model.clearWaypoints)
                        .buttonStyle(.bordered)
                        .controlSize(.small)
                        .disabled(model.waypoints.isEmpty)
                }
            }

            fileControls
        }
        .padding(.horizontal, 12)
        .padding(.top, 6)
        .popover(isPresented: $isNaming) { nameForm }
    }

    private var fileControls: some View {
        HStack(spacing: 4) {
            smallButton("Save", "square.and.arrow.down") {
                draftName = suggestedName
                isNaming = true
            }
            .disabled(model.waypoints.isEmpty)

            smallButton("Import", "arrow.down.doc") {
                if let url = FilePanels.chooseGPX() { model.importGPX(from: url) }
            }

            smallButton("Export", "arrow.up.doc") {
                if let url = FilePanels.saveGPX(defaultName: suggestedName) {
                    model.exportGPX(to: url, named: suggestedName)
                }
            }
            .disabled(model.waypoints.isEmpty)

            Spacer()
        }
    }

    private func smallButton(_ title: String, _ symbol: String, action: @escaping () -> Void)
        -> some View {
        Button(action: action) {
            Label(title, systemImage: symbol).font(.system(size: 10))
        }
        .buttonStyle(.borderless)
        .help(title)
    }

    /// Name a new route after where it starts, which is usually what it is called.
    private var suggestedName: String {
        model.waypoints.first.map { "\($0.name) route" } ?? "Route"
    }

    private var nameForm: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Save route").font(.system(size: 12, weight: .semibold))
            TextField("Name", text: $draftName)
                .textFieldStyle(.roundedBorder)
                .frame(width: 210)
                .onSubmit { commitSave() }

            if model.routeStore.contains(name: draftName.trimmingCharacters(in: .whitespaces)) {
                Label("Replaces the route already saved under this name.",
                      systemImage: "exclamationmark.triangle")
                    .font(.system(size: 10))
                    .foregroundStyle(.secondary)
            }

            HStack {
                Spacer()
                Button("Cancel") { isNaming = false }
                Button("Save") { commitSave() }
                    .keyboardShortcut(.defaultAction)
                    .disabled(draftName.trimmingCharacters(in: .whitespaces).isEmpty)
            }
        }
        .padding(14)
    }

    private func commitSave() {
        model.saveCurrentRoute(named: draftName)
        isNaming = false
    }

    private func playback(_ route: DaemonStatus.RouteStatus) -> some View {
        VStack(spacing: 5) {
            ProgressView(value: route.progress)
                .progressViewStyle(.linear)

            HStack(spacing: 6) {
                Button {
                    route.paused ? model.resumeRoute() : model.pauseRoute()
                } label: {
                    Image(systemName: route.paused ? "play.fill" : "pause.fill")
                        .font(.system(size: 10))
                }
                .buttonStyle(.bordered)
                .controlSize(.small)

                Button {
                    model.stopRoute()
                } label: {
                    Image(systemName: "stop.fill").font(.system(size: 10))
                }
                .buttonStyle(.bordered)
                .controlSize(.small)

                Spacer()

                Text("\(Int(route.progress * 100))% · \(formatDuration(route.remainingS)) left")
                    .font(.system(size: 9))
                    .foregroundStyle(.secondary)
            }
        }
    }

    private func summary(for preview: RouteService.Result) -> String {
        let metres = preview.lengthMetres
        let distance = metres >= 1000
            ? String(format: "%.1f km", metres / 1000)
            : String(format: "%.0f m", metres)
        let minutes = Int((metres / model.speed.metresPerSecond / 60).rounded())
        return "\(distance) · ~\(max(1, minutes)) min"
    }

    private func formatDuration(_ seconds: Double) -> String {
        let total = Int(seconds.rounded())
        if total < 60 { return "\(total)s" }
        let minutes = total / 60
        return minutes < 60 ? "\(minutes)m" : "\(minutes / 60)h \(minutes % 60)m"
    }
}

/// Drift and overflow, pinned under the sidebar.
struct SidebarFooter: View {
    @EnvironmentObject private var model: AppModel

    var body: some View {
        HStack(spacing: 10) {
            Toggle(isOn: Binding(
                get: { model.jitterEnabled },
                set: { _ in model.toggleJitter() }
            )) {
                Text("Drift").font(.system(size: 11))
            }
            .toggleStyle(.switch)
            .controlSize(.mini)
            .help("Wander a few metres, the way a real GPS fix does when you stand still")

            Spacer()

            Menu {
                Button("Clear History") { model.store.clearHistory() }
                Divider()
                Button("Quit Meridian") {
                    model.shutDown()
                    NSApplication.shared.terminate(nil)
                }
            } label: {
                Image(systemName: "ellipsis.circle").font(.system(size: 12))
            }
            .menuStyle(.borderlessButton)
            .menuIndicator(.hidden)
            .fixedSize()
            .foregroundStyle(.secondary)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 7)
    }
}


/// A saved route: load it back, or manage it from the context menu.
struct SavedRouteRow: View {
    @EnvironmentObject private var model: AppModel
    let route: SavedRoute

    @State private var isHovering = false

    var body: some View {
        HStack(spacing: 7) {
            Image(systemName: route.speed.symbol)
                .font(.system(size: 10))
                .foregroundStyle(.blue)
                .frame(width: 14)

            VStack(alignment: .leading, spacing: 1) {
                Text(route.name)
                    .font(.system(size: 12))
                    .lineLimit(1)
                Text(route.summary)
                    .font(.system(size: 9))
                    .foregroundStyle(.secondary)
            }

            Spacer(minLength: 4)

            if isHovering {
                Button { model.load(route) } label: {
                    Image(systemName: "arrow.up.doc.on.clipboard").font(.system(size: 10))
                }
                .buttonStyle(.borderless)
                .help("Load this route")
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 4)
        .background(isHovering ? Color.secondary.opacity(0.1) : .clear)
        .contentShape(Rectangle())
        .onHover { isHovering = $0 }
        .onTapGesture { model.load(route) }
        .contextMenu {
            Button("Load") { model.load(route) }
            Button("Export as GPX…") {
                model.load(route)
                if let url = FilePanels.saveGPX(defaultName: route.name) {
                    model.exportGPX(to: url, named: route.name)
                }
            }
            Divider()
            Button("Delete", role: .destructive) { model.routeStore.remove(route) }
        }
    }
}
