import SwiftUI

/// Owns the model for the process lifetime.
///
/// The menu bar content view is not created until the user first opens it, so
/// `onAppear` is far too late to start polling — the helper would not launch
/// until someone clicked the icon. The app delegate runs on launch.
@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    let model = AppModel()

    func applicationDidFinishLaunching(_ notification: Notification) {
        model.start()
    }

    func applicationWillTerminate(_ notification: Notification) {
        model.shutDown()
    }

    /// Clicking the Dock icon with no window open should bring the app back.
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows: Bool) -> Bool {
        true
    }
}

@main
struct MeridianApp: App {
    static let mainWindowID = "meridian.main"

    @NSApplicationDelegateAdaptor(AppDelegate.self) private var delegate

    var body: some Scene {
        Window("Meridian", id: Self.mainWindowID) {
            MainWindowView()
                .environmentObject(delegate.model)
        }
        .defaultSize(width: 1020, height: 700)
        .commands {
            CommandGroup(replacing: .newItem) {}
        }

        MenuBarExtra {
            MenuBarPreview()
                .environmentObject(delegate.model)
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
