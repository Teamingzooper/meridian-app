import SwiftUI

/// Owns the model for the process lifetime.
///
/// The menu bar content view is not created until the user first opens the
/// popover, so `onAppear` is far too late to start polling — the helper would
/// not launch until someone clicked the icon. The app delegate runs on launch.
@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    let model = AppModel()

    func applicationDidFinishLaunching(_ notification: Notification) {
        model.start()
    }

    func applicationWillTerminate(_ notification: Notification) {
        model.shutDown()
    }
}

@main
struct MeridianApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var delegate

    var body: some Scene {
        MenuBarExtra {
            RootView()
                .environmentObject(delegate.model)
                .frame(width: 420, height: 640)
        } label: {
            MenuBarLabel(model: delegate.model)
        }
        .menuBarExtraStyle(.window)
    }
}

/// The icon doubles as a status light: at a glance, is the phone somewhere it isn't?
private struct MenuBarLabel: View {
    @ObservedObject var model: AppModel

    var body: some View {
        Image(systemName: model.menuBarSymbol)
            .symbolRenderingMode(.hierarchical)
    }
}

extension AppModel {
    var menuBarSymbol: String {
        guard helperReachable else { return "location.slash" }
        switch status.mode {
        case .idle: return "location"
        case .fixed: return "location.fill"
        case .route: return "location.north.line.fill"
        }
    }
}
