# Trip Planner

Android trip planning for Israel: create a titled trip, collect locations, choose
fixed start/end points, optimize intermediate stops for driving distance, and
manually rearrange them. Travel times and turn-by-turn navigation are out of scope.
The goal is a free app without a paid routing API dependency.

## Current state

| Component | Status |
| --- | --- |
| Python/FastAPI backend | Implemented; 62 tests passed in local validation |
| OR-Tools stop ordering | Implemented; up to 20 intermediate stops |
| Routino slim routing | Implemented and tested against a real regional road database |
| GraphHopper adapter | Implemented with mocked tests; live configuration unvalidated |
| Kotlin/Compose Android app | Local trips, share intake, endpoints, optimization and manual stop ordering |
| Android build and unit tests | Debug APK, unit tests and lint passed in GitHub Actions |
| Android device testing | Not yet run on an emulator or physical phone |
| Automatic Google Maps/Waze link resolution | Web: automatic destination extraction and allowlisted short-link resolution; Android: explicit coordinate queries |
| Backend deployment | User-installed on Ubuntu; external health and routing requests verified |

Trips are stored locally on Android using Room. A small backend supplies routing
and optimization; there are no accounts or server-side trip database yet.

## Backend

Requires Python 3.12 or newer:

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.lock
.venv/bin/pip install --no-deps -e backend
cd backend
../.venv/bin/uvicorn app.main:app --reload
```

API documentation: http://127.0.0.1:8000/docs

- `GET /health`: process health and routing-provider configuration.
- `POST /v1/routes/optimize`: optimize intermediate stops between fixed endpoints.
- `POST /v1/routes/calculate`: preserve a manually selected order.

Without provider configuration, route operations return HTTP 503. No straight-line
or synthetic routing fallback is used. `.env.example` documents configuration;
variables must be exported explicitly (no automatic dotenv loading).

Requests include `revision`, `start`, `end`, optional `stops`, and `roadPolicy`.
Each point has a unique request-local ID and coordinates. For round trips, use
separate start/end IDs with equal coordinates. Responses echo the revision and
return ordered stop IDs, distance, per-leg distances, and GeoJSON geometry
(longitude, latitude). Android must discard stale calculation revisions.

## Low-memory routing: Routino

See [setup instructions](routino/README.md) for compilation, data import,
configuration and localhost-only serving. No API key or subscription is required.
Road data, downloaded source, executables and transfer bundles are intentionally
excluded from Git; reproduce them with the preparation script.

Measured on the managed development environment, **not the Ubuntu hosting VM**:

| Measurement | Result |
| --- | --- |
| Regional database | 72.57 MiB |
| Importer peak RSS | 109.33 MiB |
| Individual sample routes | 10–24.5 MiB peak RSS |
| Backend peak RSS on 20 local stops | About 72 MiB, excluding child/cache overhead |
| Complete 20-stop calculation | About 5 seconds, warm cache |

The curated profile minimizes distance within an eligible paved-car graph,
allows tolls, excludes ferries/tracks/unpaved roads, and obeys one-way/turn rules.
CLI distances have 10-meter precision. Results are optimized, not guaranteed to
be globally shortest. Point snapping, entrances, current access conditions,
production capacity and map/geocoding services need further validation.

Detailed evidence: [Routino measurements](reports/routino-validation.md).
Earlier [GraphHopper/prototype findings](reports/validation.md) are retained as
historical reports and are superseded by the Routino results where applicable.

## Tests and benchmarks

```bash
cd backend
../.venv/bin/pytest -q
../.venv/bin/python -m benchmarks.run
```

The CI workflow runs backend tests without paid services. The real Routino binary
test is skipped unless its optional fixture database is built as documented in
`routino/README.md`. Other tests use synthetic matrices or mocked HTTP responses.
Synthetic benchmark results do not establish road coverage or API performance.

## Android

Open `android/` in Android Studio. The project targets Android SDK 35, minimum
Android 8 (API 26), and includes Gradle 8.11.1, Kotlin, Compose and Room.

```bash
cd android
./gradlew :app:assembleDebug
```

A configured Android SDK and JDK 17 are required. The current update passed
local debug APK compilation, 20 unit tests, and lint. GitHub Actions runs the
same checks and publishes a `trip-planner-debug` artifact (retained seven days)
under the [latest Android build](https://github.com/zvipev10/trip-planner/actions/workflows/android.yml).
Download its ZIP, extract `app-debug.apk`, and install it on Android 8+.
No emulator or physical-device test has been recorded yet. Addresses and
short links can be collected unresolved; confirm their coordinates before routing.
Android supports optimization, distance results, and manual intermediate-stop
ordering with distance recalculation. Start and end stay fixed and may reference
the same saved location. Route results last while the trip is open; locations
and endpoints persist in Room. Map display is not implemented.

Debug builds connect to `http://151.145.93.180/trip-planner/`; cleartext HTTP is
permitted only for that host. Release builds require configuring `API_URL` in
`android/app/build.gradle.kts` with an HTTPS backend URL. Android sends no trip
title or place names to the routing API, only IDs and coordinates.

To deploy the backend changes on the existing VM:

```bash
cd /home/ubuntu/trip-planner
git pull --ff-only
.venv/bin/python -m pip install --no-deps -e ./backend
sudo systemctl restart trip-planner
```

The API paths and request format are unchanged; both web and Android clients
use the same optimization and manual-calculation endpoints.

## Repository boundaries

Credentials, SSH keys, `.env`, local environments, Android SDKs, build outputs,
regional road files and binary setup bundles must stay outside Git. See
[third-party notices](THIRD_PARTY_NOTICES.md) for the derived Routino profile,
upstream licenses and OpenStreetMap data attribution.


Android validation details: [build report](reports/android-validation.md).
The CI workflow builds and publishes a debug APK on pushes and pull requests.
This is a development build, not a signed production release. Local trip/location
editing, endpoint selection and routing are implemented. Map display still
requires implementation. Failed calculations preserve the current manual order
so the user can retry; edits invalidate results and cancel in-flight requests.


## iOS

A native SwiftUI prototype is in [ios/](ios/README.md), for iOS 17+. It includes
local trips/locations, endpoint selection, route optimization against the existing
VM API, ordered results and total distance. An iOS Simulator CI workflow builds
and tests it without Apple signing credentials. Physical iPhone installation
requires Xcode provisioning or TestFlight; simulator artifacts are not phone apps.
See the iOS README for steps and current limitations.


## Mobile web (Safari / Android browsers)

The buildless web app is served by FastAPI at `/web/` and calls the same-origin
HTTP API. On the existing VM proxy, its URL after deployment is
`http://151.145.93.180/trip-planner/web/`. It supports titled trips, local storage,
pasted locations, endpoints, optimized order/distance, manual reordering with
recalculation, backups and an interactive OpenStreetMap street map with the
route, labeled stops, zoom/pan, popups and a full-route view. See [deployment instructions](web/README.md).
No signing, paid browser SDK, or frontend Node server is needed. Names are optional;
map-link paste extracts destination coordinates and a name automatically when
available, otherwise assigns a numbered name. Short links are resolved through
`POST /v1/places/resolve` with bounded requests and allowlisted redirect hosts.
Plain addresses and links without exposed destination data remain unresolved. The code is ready for deployment;
the VM must pull the update and restart its service.
