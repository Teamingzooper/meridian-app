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
        ),
        .testTarget(
            name: "MeridianTests",
            dependencies: ["Meridian"],
            path: "Tests/MeridianTests",
            swiftSettings: [.swiftLanguageMode(.v5)]
        )
    ]
)
