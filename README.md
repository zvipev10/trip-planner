# Trip Planner

Android trip planning for Israel: create a titled trip, collect locations, choose
fixed start/end points, optimize intermediate stops for driving distance, and
manually rearrange them. Travel times and turn-by-turn navigation are out of scope.
The goal is a free app without a paid routing API dependency.

## Current state

| Component | Status |
| --- | --- |
| Python/FastAPI backend | Implemented; 35 tests passed in local validation |
| OR-Tools stop ordering | Implemented; up to 20 intermediate stops |
| Routino slim routing | Implemented and tested against a real regional road database |
| GraphHopper adapter | Implemented with mocked tests; live configuration unvalidated |
| Kotlin/Compose Android app | Work in progress; local trips, location editing, share intake and endpoints authored |
| Android build and unit tests | Debug APK, unit tests and lint passed in GitHub Actions |
| Android device testing | Not yet run on an emulator or physical phone |
| Automatic Google Maps/Waze link resolution | Not implemented; Android preserves links and extracts explicit coordinate queries |
| Production deployment | Not deployed; user's Ubuntu VM remains unchanged |

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

A configured Android SDK and JDK 17 are required. GitHub Actions has successfully
built the debug APK and passed unit tests and lint. See the
[verified build](https://github.com/zvipev10/trip-planner/actions/runs/39047260207)
and its `trip-planner-debug` artifact (retained for seven days). Download the ZIP,
extract `app-debug.apk`, and install it on an Android 8+ device for testing.
No emulator or physical-device test has been recorded yet. Addresses and
short links can be collected unresolved; route calculation and map display are
not wired into the Android UI yet. Start and end can reference the same location.

## Repository boundaries

Credentials, SSH keys, `.env`, local environments, Android SDKs, build outputs,
regional road files and binary setup bundles must stay outside Git. See
[third-party notices](THIRD_PARTY_NOTICES.md) for the derived Routino profile,
upstream licenses and OpenStreetMap data attribution.


Android validation details: [build report](reports/android-validation.md).
The CI workflow builds and publishes a debug APK on pushes and pull requests.
This is a development build, not a signed production release. Local trip/location
editing and endpoint selection are implemented; routing and map display remain
backend-only and are not yet connected to the Android screens.
