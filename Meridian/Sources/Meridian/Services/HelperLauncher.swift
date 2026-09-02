import Foundation

/// Starts and supervises the `meridiand` sidecar.
///
/// The app is useless without it, so rather than telling the user to open a
/// terminal, we start it ourselves. The helper's output is teed to a log file:
/// a background process that dies silently is impossible to diagnose otherwise.
@MainActor
final class HelperLauncher {
    private var process: Process?

    /// The last failure, so the UI can say more than "it didn't work".
    private(set) var lastFailure: String?

    private var supportDirectory: URL {
        FileManager.default.homeDirectoryForCurrentUser
            .appending(path: "Library/Application Support/Meridian")
    }

    /// Where setup records the helper's launch command, one argument per line.
    private var commandFileURL: URL {
        supportDirectory.appending(path: "helper-command")
    }

    var logURL: URL {
        FileManager.default.homeDirectoryForCurrentUser
            .appending(path: "Library/Logs/Meridian-helper.log")
    }

    var isLaunched: Bool { process?.isRunning == true }

    /// Resolve the helper command, preferring what setup recorded.
    private func resolveCommand() -> [String]? {
        if let raw = try? String(contentsOf: commandFileURL, encoding: .utf8) {
            let parts = raw.split(separator: "\n")
                .map { $0.trimmingCharacters(in: .whitespaces) }
                .filter { !$0.isEmpty }
            if let first = parts.first, FileManager.default.isExecutableFile(atPath: first) {
                return parts
            }
            lastFailure = "The recorded helper command is not runnable: \(parts.first ?? "empty")"
        }

        for candidate in ["/opt/homebrew/bin/meridiand", "/usr/local/bin/meridiand"] {
            if FileManager.default.isExecutableFile(atPath: candidate) { return [candidate] }
        }

        if lastFailure == nil {
            lastFailure = "No helper found. Run scripts/setup.sh in the Meridian folder."
        }
        return nil
    }

    /// A file handle for the helper's log, so a crash leaves a trace on disk.
    private func openLog() -> FileHandle? {
        let manager = FileManager.default
        try? manager.createDirectory(
            at: logURL.deletingLastPathComponent(), withIntermediateDirectories: true
        )
        if !manager.fileExists(atPath: logURL.path) {
            manager.createFile(atPath: logURL.path, contents: nil)
        }
        guard let handle = try? FileHandle(forWritingTo: logURL) else { return nil }
        // Start each run from empty so the log always describes the current attempt.
        try? handle.truncate(atOffset: 0)
        return handle
    }

    /// Launch the helper. Returns false when it could not be found or started.
    @discardableResult
    func launch() -> Bool {
        guard !isLaunched else { return true }

        lastFailure = nil
        guard let command = resolveCommand() else { return false }

        let task = Process()
        task.executableURL = URL(fileURLWithPath: command[0])
        task.arguments = Array(command.dropFirst())
        // Launched from Finder there is no console, so give it a real cwd and env.
        task.currentDirectoryURL = FileManager.default.homeDirectoryForCurrentUser

        if let log = openLog() {
            task.standardOutput = log
            task.standardError = log
        }

        do {
            try task.run()
            process = task
            return true
        } catch {
            lastFailure = "Couldn't start the helper: \(error.localizedDescription)"
            return false
        }
    }

    /// Why the helper stopped, read back from its log.
    func recentLog(lines: Int = 12) -> String? {
        guard let contents = try? String(contentsOf: logURL, encoding: .utf8) else { return nil }
        let tail = contents.split(separator: "\n").suffix(lines).joined(separator: "\n")
        return tail.isEmpty ? nil : tail
    }

    func terminate() {
        process?.terminate()
        process = nil
    }
}
