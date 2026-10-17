# Native iOS implementation — 2026-10-17

SwiftUI application in `ios/`, targeting iOS 17+, with XcodeGen project generation.

Implemented: titled trips, local atomic JSON persistence, location editing,
explicit-coordinate extraction from pasted links, separate fixed start/end points,
round trips, distance-based backend optimization, ordered results and saved plans.
Edits invalidate results; asynchronous responses are rejected after a revision
change. No SwiftData migration or external paid SDK is required.

API integration uses `http://151.145.93.180/trip-planner/` in Debug. A direct live
request from the development environment to `v1/routes/optimize`, with two public
Tel Aviv test coordinates and no intermediate stops, returned revision 0, status
`optimized`, 3,290 meters, one matching leg and geometry with 89 points. This
validates the endpoint and wire contract; it is not a physical-iPhone test.

CI: https://github.com/zvipev10/trip-planner/actions/runs/39055761439

The first compiler pass identified two Swift error-variable shadowing mistakes;
those assignments are fixed in commit `2906eac9024b3911399bc81d08039f7cbaa35675`.
The corrected simulator build and all tests completed successfully in that run.
Nine XCTest cases cover endpoints, round trips, coordinate requirements, stop
limits, stale/missing results, JSON encoding, shared links, persistence, endpoint
removal and preservation of unreadable storage. Simulator verification is distinct from physical-iPhone installation.

Debug permits HTTP for the current endpoint. Release disallows that exception and
rejects the HTTP base URL. A production/TestFlight version needs HTTPS and signing.
No Apple credentials, development team, signing certificates or provisioning
profiles were added. Simulator artifacts cannot be installed on an iPhone.

The user has neither a Mac with Xcode nor paid Apple Developer membership. Thus
this native source does not yet provide an installable app for their phone. A
Safari version is now implemented for phone testing, with a VM code update required. No iPhone installation or physical-device validation was done.

Not yet implemented: Share Extension, automatic short-link/address resolution,
route maps, manual route rearrangement and account synchronization.
