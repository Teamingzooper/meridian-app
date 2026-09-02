import SwiftUI

/// Transient feedback: what happened, or what to go do about it.
struct BannerView: View {
    let banner: AppModel.Banner
    let dismiss: () -> Void

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: symbol)
                .foregroundStyle(tint)
            Text(banner.message)
                .font(.system(size: 11))
                .fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 4)
            Button(action: dismiss) {
                Image(systemName: "xmark")
                    .font(.system(size: 9, weight: .bold))
            }
            .buttonStyle(.borderless)
            .foregroundStyle(.secondary)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 8)
        .background(tint.opacity(0.12))
    }

    private var symbol: String {
        switch banner.kind {
        case .error: return "exclamationmark.triangle.fill"
        case .notice: return "info.circle.fill"
        case .success: return "checkmark.circle.fill"
        }
    }

    private var tint: Color {
        switch banner.kind {
        case .error: return .red
        case .notice: return .orange
        case .success: return .green
        }
    }
}
