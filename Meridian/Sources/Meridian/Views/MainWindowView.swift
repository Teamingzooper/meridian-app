import SwiftUI

/// The full app: places and routes in one scrolling sidebar, map filling the rest.
struct MainWindowView: View {
    @EnvironmentObject private var model: AppModel

    var body: some View {
        NavigationSplitView {
            SidebarView()
                .navigationSplitViewColumnWidth(min: 250, ideal: 280, max: 360)
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
        .frame(minWidth: 860, minHeight: 580)
    }
}
