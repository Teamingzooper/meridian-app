import SwiftUI

/// The "you are here" dot: green, to read as distinct from the blue simulated pin.
struct RealLocationDot: View {
    var body: some View {
        ZStack {
            Circle()
                .fill(.green.opacity(0.22))
                .frame(width: 24, height: 24)
            Circle()
                .fill(.green)
                .frame(width: 12, height: 12)
                .overlay(Circle().stroke(.white, lineWidth: 2))
                .shadow(radius: 1)
        }
        .accessibilityLabel("Your real location")
    }
}
