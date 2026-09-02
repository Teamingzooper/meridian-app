import AppKit
import UniformTypeIdentifiers

/// Open and save panels for GPX files.
///
/// Wrapped rather than inlined so the views stay free of AppKit, and so the
/// GPX type is resolved in one place — `.gpx` has no system-declared UTType, so
/// it has to be built from the filename extension with a plain-text fallback.
enum FilePanels {
    static var gpxType: UTType {
        UTType(filenameExtension: "gpx") ?? .xml
    }

    static func chooseGPX() -> URL? {
        let panel = NSOpenPanel()
        panel.title = "Import a GPX route"
        panel.allowedContentTypes = [gpxType, .xml]
        panel.allowsMultipleSelection = false
        panel.canChooseDirectories = false
        return panel.runModal() == .OK ? panel.url : nil
    }

    static func saveGPX(defaultName: String) -> URL? {
        let panel = NSSavePanel()
        panel.title = "Export route as GPX"
        panel.allowedContentTypes = [gpxType]
        panel.nameFieldStringValue = sanitised(defaultName) + ".gpx"
        return panel.runModal() == .OK ? panel.url : nil
    }

    /// Keep a route name usable as a filename.
    private static func sanitised(_ name: String) -> String {
        let cleaned = name.components(separatedBy: CharacterSet(charactersIn: "/\\:*?\"<>|"))
            .joined(separator: "-")
            .trimmingCharacters(in: .whitespacesAndNewlines)
        return cleaned.isEmpty ? "route" : cleaned
    }
}
