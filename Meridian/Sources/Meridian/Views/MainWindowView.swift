import SwiftUI

/// The full app: a sidebar for places and routes, and a map with room to work.
struct MainWindowView: View {
    @EnvironmentObject private var model: AppModel
    @State private var sidebar: SidebarSection = .saved

    enum SidebarSection: String, CaseIterable, Identifiable {
        case saved = "Saved"
        case route = "Route"
        var id: String { rawValue }
    }

    var body: some View {
        NavigationSplitView {
            VStack(spacing: 0) {
                StatusHeader()

                Picker("", selection: $sidebar) {
                    ForEach(SidebarSection.allCases) { Text($0.rawValue).tag($0) }
                }
                .pickerStyle(.segmented)
                .labelsHidden()
                .padding(.horizontal, 10)
                .padding(.vertical, 8)

                Divider()

                switch sidebar {
                case .saved: SavedPane()
                case .route: RoutePane()
                }

                Divider()
                SidebarFooter()
            }
            .navigationSplitViewColumnWidth(min: 240, ideal: 270, max: 340)
        } detail: {
            VStack(spacing: 0) {
                if let banner = model.banner {
                    BannerView(banner: banner) { model.banner = nil }
                }
                MapPane()
            }
            .navigationTitle("Meridian")
        }
        .animation(.easeInOut(duration: 0.18), value: model.banner)
        .frame(minWidth: 820, minHeight: 560)
    }
}

/// Drift toggle and overflow, tucked under the sidebar.
private struct SidebarFooter: View {
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
