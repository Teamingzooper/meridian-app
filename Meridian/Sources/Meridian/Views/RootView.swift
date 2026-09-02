import SwiftUI

struct RootView: View {
    @EnvironmentObject private var model: AppModel
    @State private var pane: Pane = .map

    enum Pane: String, CaseIterable, Identifiable {
        case map = "Map"
        case route = "Route"
        case saved = "Saved"

        var id: String { rawValue }
    }

    var body: some View {
        VStack(spacing: 0) {
            StatusHeader()

            if let banner = model.banner {
                BannerView(banner: banner) { model.banner = nil }
                    .transition(.move(edge: .top).combined(with: .opacity))
            }

            Picker("", selection: $pane) {
                ForEach(Pane.allCases) { Text($0.rawValue).tag($0) }
            }
            .pickerStyle(.segmented)
            .labelsHidden()
            .padding(.horizontal, 12)
            .padding(.vertical, 8)

            Divider()

            switch pane {
            case .map: MapPane()
            case .route: RoutePane()
            case .saved: SavedPane { pane = .map }
            }

            Divider()
            FooterBar()
        }
        .animation(.easeInOut(duration: 0.18), value: model.banner)
        // Clear stale feedback when the user moves to another pane.
        .onChange(of: pane) { model.banner = nil }
    }
}

/// Jitter toggle and quit, out of the way at the bottom.
private struct FooterBar: View {
    @EnvironmentObject private var model: AppModel

    var body: some View {
        HStack(spacing: 10) {
            Toggle(isOn: Binding(
                get: { model.jitterEnabled },
                set: { _ in model.toggleJitter() }
            )) {
                Text("Drift")
                    .font(.system(size: 11))
            }
            .toggleStyle(.switch)
            .controlSize(.mini)
            .help("Wander a few metres, the way a real GPS fix does when you stand still")

            Spacer()

            if let device = model.status.device {
                Text(device.name)
                    .font(.system(size: 10))
                    .foregroundStyle(.tertiary)
                    .lineLimit(1)
            }

            // Quit lives behind a menu so the header toggle is the only on/off control.
            Menu {
                Button("Clear History") { model.store.clearHistory() }
                Divider()
                Button("Quit Meridian") {
                    model.shutDown()
                    NSApplication.shared.terminate(nil)
                }
            } label: {
                Image(systemName: "ellipsis.circle")
                    .font(.system(size: 12))
            }
            .menuStyle(.borderlessButton)
            .menuIndicator(.hidden)
            .fixedSize()
            .foregroundStyle(.secondary)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 7)
    }
}
