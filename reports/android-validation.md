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


## Android 0.3.0 map update — 2026-10-20

The APK now includes a Leaflet/OpenStreetMap route map inside an Android WebView.
The API geometry is retained as GeoJSON longitude/latitude pairs and converted by
the shared map renderer. The map shows start/end and numbered stops, safe text
popups, zoom/pan, full-route fitting and tile retry controls. Round-trip endpoints
combine into S/E. Reordering clears the road line and hides the map until manual
recalculation; editing trips invalidates results as before.

Leaflet JS/CSS/license and the shared renderer are copied from the backend source
into generated Android assets during preBuild. All six map assets were verified
inside the APK ZIP. HTML/CSS are Android assets. A restricted HTTPS asset origin
serves only known bundled files; external content is limited to OpenStreetMap
tiles. JavaScript is used for the bundled map, with no JavaScript/native bridge,
file access or mixed HTTP map content. Attribution links open the external
browser. Lifecycle pause/resume/release and nested map gestures are handled.
Identical payloads avoid resetting the user's map view on recomposition.

Local JDK 17/SDK 35 validation passed assembleDebug, 25 JVM tests, and lintDebug
with zero lint errors. Five new map tests cover geometry order/bounds, stop order,
round trips and stale results. The Retrofit transport test now includes geometry.
An additional Chromium 360×440 check loaded assets extracted directly from the
APK at the same HTTPS origin as the WebView. Live map tiles returned HTTP 200;
route lines, accessible markers, escaped popup labels, zoom/fit, redraw and a
round trip passed without page errors or horizontal overflow. Its route payload
was a fixture. This browser check does not substitute for an Android emulator or
physical-device test, neither of which is available in this environment.

No backend deployment or paid map key is needed for this Android map. The existing
backend already returns route geometry. Google/Waze short-link resolution and
optional imported names remain web-only in this update.
