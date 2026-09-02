import Foundation

extension Comparable {
    /// Constrain a value to a range, for camera distances and similar bounded maths.
    func clamped(to range: ClosedRange<Self>) -> Self {
        min(max(self, range.lowerBound), range.upperBound)
    }
}
