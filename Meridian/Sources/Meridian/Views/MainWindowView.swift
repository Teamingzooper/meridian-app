import SwiftUI

/// The full app: sidebar and map side by side.
///
/// Uses `HSplitView` rather than `NavigationSplitView`. On macOS 26 the latter
/// floats the sidebar as a translucent panel over the detail view, so the map ran
/// underneath it. A split view tiles the two, giving the map its own edge to
/// start from, and the divider stays draggable.
struct MainWindowView: View {
    @EnvironmentObject private var model: AppModel

    var body: some View {
        HSplitView {
            SidebarView()
                .frame(minWidth: 250, idealWidth: 285, maxWidth: 380)
                .background(.background)

            VStack(spacing: 0) {
                if let banner = model.banner {
                    BannerView(banner: banner) { model.banner = nil }
                }
                MapPane()
            }
            .frame(minWidth: 520)
            .animation(.easeInOut(duration: 0.18), value: model.banner)
        }
        .frame(minWidth: 860, minHeight: 580)
        .navigationTitle("Meridian")
    }
}
