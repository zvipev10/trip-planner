# Android backend integration validation — 2026-10-17

Android 0.2.0 now connects to the routing backend for optimized driving distance,
fixed endpoints (including round trips), and manual intermediate-stop ordering
with distance recalculation. Debug HTTP is restricted to `151.145.93.180`;
release builds require configuring an HTTPS API URL.

Local validation used JDK 17, Android SDK 35 and Gradle 8.11.1:

```text
:app:assembleDebug       PASSED
:app:testDebugUnitTest   PASSED (20 tests)
:app:lintDebug           PASSED (0 errors)
```

The APK is generated at `android/app/build/outputs/apk/debug/app-debug.apk`.
GitHub Actions runs these same tasks and publishes `trip-planner-debug` on each
push; artifacts are retained for seven days. The APK is debug signed.

Eight share-parser tests cover Google/Waze explicit coordinate queries,
malformed coordinates, Hebrew labels and rejection of camera positions.
Eleven routing-contract tests cover fixed endpoints, round trips, unresolved
coordinates, stop limits, manual ordering, stale revisions and invalid distances.
One MockWebServer test verifies both Retrofit endpoints, the `/trip-planner/`
proxy prefix, JSON serialization and response validation.

A Room transaction reads the trip and locations together. Revision and request
generation checks reject obsolete responses after edits, cancellation or trip
selection changes. Route plans remain in memory while the trip is open;
locations and endpoints persist using the unchanged Room v1 schema. The exported
schema is included for future migration checks.

Backend tests: 39 passed. Web regression tests: 13 passed. Live HTTP calls to
both `/trip-planner/v1/routes/optimize` and `/trip-planner/v1/routes/calculate`
returned HTTP 200, revision 7, empty intermediate-stop lists and 3,290 meters
for the two-point test request. This verifies the existing VM API accepts the
Android request format; the backend source changes still require deployment.

No emulator or physical-device run has been performed. UI interactions,
share-sheet behavior, persistence across restarts and RTL layout still require
Android device testing. Automatic address/short-link resolution and Android
map display are not implemented. Non-blocking lint warnings concern dependency
updates, the existing backup configuration and a missing application icon.
