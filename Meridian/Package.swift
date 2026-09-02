// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "Meridian",
    platforms: [.macOS(.v14)],
    targets: [
        .executableTarget(
            name: "Meridian",
            path: "Sources/Meridian",
            swiftSettings: [.swiftLanguageMode(.v5)]
        )
    ]
)
