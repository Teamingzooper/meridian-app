import SwiftUI

/// The menu bar item: a glance at what the phone is doing, plus the controls you
/// actually reach for mid-task. Anything that needs room lives in the main window.
struct MenuBarPreview: View {
    @EnvironmentObject private var model: AppModel
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        VStack(spacing: 0) {
            StatusHeader()

            if model.status.mode == .route, let route = model.status.route {
                routeStrip(route)
                Divider()
            }

            recents

            Divider()
            footer
        }
        .frame(width: 300)
    }

    // MARK: - Route progress

    private func routeStrip(_ route: DaemonStatus.RouteStatus) -> some View {
        VStack(spacing: 6) {
            ProgressView(value: route.progress)
                .progressViewStyle(.linear)

            HStack(spacing: 8) {
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

                Text("\(Int(route.progress * 100))%")
                    .font(.system(size: 10, weight: .medium, design: .rounded))
                    .foregroundStyle(.secondary)
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
    }

    // MARK: - Quick jump

    /// The handful of places worth reaching without opening the window.
    private var quickPlaces: [Place] {
        let bookmarks = model.store.bookmarks.prefix(4)
        if !bookmarks.isEmpty { return Array(bookmarks) }
        return Array(model.store.history.prefix(4))
    }

    private var recents: some View {
        VStack(alignment: .leading, spacing: 0) {
            if quickPlaces.isEmpty {
                Text("Star a place to jump to it from here.")
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 10)
            } else {
                Text(model.store.bookmarks.isEmpty ? "RECENT" : "BOOKMARKS")
                    .font(.system(size: 9, weight: .semibold))
                    .foregroundStyle(.tertiary)
                    .padding(.horizontal, 12)
                    .padding(.top, 8)
                    .padding(.bottom, 3)

                ForEach(quickPlaces) { place in
                    Button {
                        model.apply(place)
                    } label: {
                        HStack(spacing: 6) {
                            Circle()
                                .fill(isCurrent(place) ? Color.blue : Color.secondary.opacity(0.35))
                                .frame(width: 6, height: 6)
                            Text(place.name)
                                .font(.system(size: 12))
                                .lineLimit(1)
                            Spacer()
                        }
                        .padding(.horizontal, 12)
                        .padding(.vertical, 5)
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                }
                .padding(.bottom, 6)
            }
        }
    }

    private func isCurrent(_ place: Place) -> Bool {
        guard let simulated = model.simulatedCoordinate else { return false }
        return place.isEffectivelySame(as: simulated)
    }

    // MARK: - Footer

    private var footer: some View {
        HStack(spacing: 8) {
            Button {
                openWindow(id: MeridianApp.mainWindowID)
                NSApplication.shared.activate(ignoringOtherApps: true)
            } label: {
                Label("Open Meridian", systemImage: "map")
                    .font(.system(size: 11))
            }
            .buttonStyle(.borderless)

            Spacer()

            Button {
                model.shutDown()
                NSApplication.shared.terminate(nil)
            } label: {
                Image(systemName: "power").font(.system(size: 11))
            }
            .buttonStyle(.borderless)
            .foregroundStyle(.secondary)
            .help("Quit Meridian")
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
    }
}
