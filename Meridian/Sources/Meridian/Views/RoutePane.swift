import CoreLocation
import SwiftUI

/// Build a path from waypoints, then walk, bike or drive it.
struct RoutePane: View {
    @EnvironmentObject private var model: AppModel

    var body: some View {
        VStack(spacing: 0) {
            if model.waypoints.isEmpty {
                emptyState
            } else {
                waypointList
                Divider()
                controls
            }

            if let route = model.status.route {
                Divider()
                playbackBar(route)
            }
        }
    }

    private var emptyState: some View {
        VStack(spacing: 8) {
            Spacer()
            Image(systemName: "point.topleft.down.to.point.bottomright.curvepath")
                .font(.system(size: 28))
                .foregroundStyle(.tertiary)
            Text("No route yet")
                .font(.system(size: 13, weight: .medium))
            Text("Pick places on the Map tab and add them with the path button.")
                .font(.system(size: 11))
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 40)
            Spacer()
        }
    }

    private var waypointList: some View {
        List {
            ForEach(Array(model.waypoints.enumerated()), id: \.element.id) { index, place in
                HStack(spacing: 8) {
                    Text("\(index + 1)")
                        .font(.system(size: 10, weight: .bold, design: .rounded))
                        .foregroundStyle(.white)
                        .frame(width: 17, height: 17)
                        .background(Circle().fill(.purple))

                    VStack(alignment: .leading, spacing: 1) {
                        Text(place.name)
                            .font(.system(size: 12))
                            .lineLimit(1)
                        Text(place.prettyCoordinates)
                            .font(.system(size: 9, design: .monospaced))
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                }
                .listRowInsets(EdgeInsets(top: 3, leading: 8, bottom: 3, trailing: 8))
            }
            .onDelete { model.removeWaypoint(at: $0) }
        }
        .listStyle(.plain)
        .frame(maxHeight: .infinity)
    }

    private var controls: some View {
        VStack(spacing: 9) {
            Picker("", selection: $model.speed) {
                ForEach(SpeedPreset.allCases) { preset in
                    Label(preset.label, systemImage: preset.symbol).tag(preset)
                }
            }
            .pickerStyle(.segmented)
            .labelsHidden()
            .onChange(of: model.speed) {
                // Walking and driving snap to different networks, so re-route.
                Task { await model.refreshRoutePreview() }
            }

            HStack(spacing: 8) {
                Toggle("Loop", isOn: $model.loopRoute)
                    .toggleStyle(.switch)
                    .controlSize(.mini)
                    .font(.system(size: 11))

                Spacer()

                if model.routing.isRouting {
                    ProgressView().controlSize(.mini)
                } else if let preview = model.routePreview {
                    Text(summary(for: preview))
                        .font(.system(size: 10))
                        .foregroundStyle(.secondary)
                }
            }

            HStack(spacing: 8) {
                Button {
                    model.playRoute()
                } label: {
                    Label("Start", systemImage: "play.fill")
                        .font(.system(size: 12, weight: .medium))
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .disabled(model.routePreview == nil || model.status.mode == .route)

                Button("Clear", action: model.clearWaypoints)
                    .buttonStyle(.bordered)
                    .font(.system(size: 12))
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
    }

    private func summary(for preview: RouteService.Result) -> String {
        let metres = preview.lengthMetres
        let distance = metres >= 1000
            ? String(format: "%.1f km", metres / 1000)
            : String(format: "%.0f m", metres)
        let minutes = Int((metres / model.speed.metresPerSecond / 60).rounded())
        return "\(distance) · about \(max(1, minutes)) min"
    }

    private func playbackBar(_ route: DaemonStatus.RouteStatus) -> some View {
        VStack(spacing: 7) {
            ProgressView(value: route.progress)
                .progressViewStyle(.linear)

            HStack(spacing: 8) {
                Button {
                    route.paused ? model.resumeRoute() : model.pauseRoute()
                } label: {
                    Label(
                        route.paused ? "Resume" : "Pause",
                        systemImage: route.paused ? "play.fill" : "pause.fill"
                    )
                    .font(.system(size: 11))
                }
                .buttonStyle(.bordered)

                Button {
                    model.stopRoute()
                } label: {
                    Label("Stop", systemImage: "stop.fill")
                        .font(.system(size: 11))
                }
                .buttonStyle(.bordered)

                Spacer()

                Text("\(Int(route.progress * 100))%")
                    .font(.system(size: 11, weight: .medium, design: .rounded))
                    .foregroundStyle(.secondary)
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
    }
}

extension RouteService.Result {
    /// Total path length in metres, for the distance and duration estimate.
    var lengthMetres: Double {
        zip(coordinates, coordinates.dropFirst()).reduce(0) { total, pair in
            let (a, b) = pair
            return total + CLLocation(latitude: a.latitude, longitude: a.longitude)
                .distance(from: CLLocation(latitude: b.latitude, longitude: b.longitude))
        }
    }
}
