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

                if model.status.mode != .idle {
                    Button("Reset", action: model.clearLocation)
                        .buttonStyle(.borderless)
                        .font(.system(size: 11))
                        .help("Give the phone its real GPS back")
                }
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
