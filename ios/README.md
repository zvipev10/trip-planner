# Native iOS prototype

SwiftUI, iOS 17+, local Codable JSON storage, and URLSession. Uses the existing
Routino/FastAPI backend at `http://151.145.93.180/trip-planner/` in Debug builds.
No paid map/routing SDK is included. The backend URL lives in `RouteClient.swift`.

Includes titled trips, place editing, pasted addresses/links, explicit-coordinate
extraction, separate start/end selection (including round trips), optimization,
ordered stop lists and approximate total distance. Trips and validated route
results save atomically on device. Edits invalidate the route, and stale API
responses cannot replace a changed trip. Failed saves keep the editor open.

Not included: an iOS Share Extension, automatic address/short-link resolution,
map rendering, manual route rearrangement, synchronization, or TestFlight signing.
Unresolved places can be collected, but require coordinates before optimization.

## Run on your iPhone using a Mac

1. Install Xcode (with iOS 17+ SDK) and Homebrew's XcodeGen: `brew install xcodegen`.
2. In this directory run `xcodegen generate`, then open `TripPlanner.xcodeproj`.
3. Select the TripPlanner app target → Signing & Capabilities. Choose your Apple
   development team and a unique bundle identifier. No team or key is committed.
4. Connect your iPhone, trust the Mac, and enable Developer Mode when requested.
5. Select the phone as the run destination and press Run with Debug configuration.

Free Apple-account provisioning is suitable for personal testing, with periodic
re-signing (typically seven days) and Apple's device/app limitations. TestFlight
requires Apple Developer Program membership and a signed distribution build.
A simulator `.app` artifact cannot be installed on a physical iPhone.

## Simulator and tests

```bash
xcodegen generate
xcodebuild -project TripPlanner.xcodeproj -scheme TripPlanner \
  -configuration Debug -destination 'platform=iOS Simulator,name=iPhone 16' \
  CODE_SIGNING_ALLOWED=NO test
```

Choose a simulator installed on your Mac. GitHub Actions selects an available
simulator automatically, tests without Apple credentials, and uploads its build
and test results. Debug builds allow HTTP solely for the current test endpoint;
Release disables this exception and refuses the HTTP URL. HTTPS configuration
is required before any production/TestFlight release. The public test backend
currently has no client authentication; no production keys are embedded.
