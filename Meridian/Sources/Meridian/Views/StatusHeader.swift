import SwiftUI

/// Device state and the current simulated position, always visible.
struct StatusHeader: View {
    @EnvironmentObject private var model: AppModel

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 8) {
                Circle()
                    .fill(indicatorColor)
                    .frame(width: 8, height: 8)

                Text(title)
                    .font(.system(size: 13, weight: .semibold))
                    .lineLimit(1)

                Spacer()

                Button(action: model.hide) {
                    Image(systemName: model.isHidden ? "eye.slash.fill" : "eye.slash")
                        .font(.system(size: 11))
                }
                .buttonStyle(.borderless)
                .foregroundStyle(model.isHidden ? Color.accentColor : .secondary)
                .help(model.store.hidePlace.map {
                    "Jump to your decoy, \($0.name). Apps see the decoy instead of where you are — "
                    + "this does not switch Location Services off."
                } ?? "Set a decoy first: right-click a saved place and choose Use as Hide Location.")

                Text(model.isSimulating ? "On" : "Off")
                    .font(.system(size: 10, weight: .medium))
                    .foregroundStyle(model.isSimulating ? .primary : .secondary)
                    .monospacedDigit()

                Toggle("", isOn: Binding(
                    get: { model.isSimulating },
                    set: { model.setSimulating($0) }
                ))
                .toggleStyle(.switch)
                .controlSize(.small)
                .labelsHidden()
                .disabled(!model.canToggle)
                .help(model.isSimulating
                      ? "Switch off and give the phone its real GPS back"
                      : "Switch back on at \(model.lastApplied?.name ?? "the last place")")
            }

            Text(subtitle)
                .font(.system(size: 11))
                .foregroundStyle(.secondary)
                .lineLimit(1)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
        .background(.quaternary.opacity(0.4))
    }

    private var indicatorColor: Color {
        guard model.helperReachable else { return .secondary }
        if model.status.error != nil { return .orange }
        switch model.status.mode {
        case .idle: return model.status.connected ? .green : .secondary
        case .fixed: return .blue
        case .route: return .purple
        }
    }

    private var title: String {
        guard model.helperReachable else { return "Starting helper…" }
        if let device = model.status.device { return device.name }
        return "No iPhone connected"
    }

    private var subtitle: String {
        if let error = model.status.error { return error.message }

        guard let device = model.status.device else {
            return "Connect your iPhone with a USB cable."
        }

        switch model.status.mode {
        case .idle:
            if let last = model.lastApplied {
                return "Real GPS · switch on for \(last.name)"
            }
            return "iOS \(device.iosVersion) · real GPS"
        case .fixed:
            guard let location = model.status.location else { return "Simulating a location" }
            return String(format: "Simulating %.5f, %.5f", location.lat, location.lon)
        case .route:
            guard let route = model.status.route else { return "Following a route" }
            let percent = Int(route.progress * 100)
            let state = route.paused ? "Paused" : "Moving"
            return "\(state) · \(percent)% · \(formatDuration(route.remainingS)) left"
        }
    }

    private func formatDuration(_ seconds: Double) -> String {
        let total = Int(seconds.rounded())
        if total < 60 { return "\(total)s" }
        let minutes = total / 60
        if minutes < 60 { return "\(minutes)m" }
        return "\(minutes / 60)h \(minutes % 60)m"
    }
}
