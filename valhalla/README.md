# Israel Valhalla deployment

Experimental driving service alongside the Trip Planner API. Production remains Routino until the backend adapter and road-policy/arrival behavior are accepted. Service binds **127.0.0.1:8002 only**. It processes one request at a time using one Actor and Python's synchronous HTTPServer. No public demo dependency or API key.

## Prebuild on a Windows workstation

Use Python 3.12+ in a separate virtualenv and install `valhalla/build-requirements.txt`. Run:

```powershell
python valhalla/build_israel.py --work-dir C:/private/valhalla-israel-build
```

The script verifies the pinned 2026-10-21 Geofabrik Israel-and-Palestine extract, builds regional timezone polygons and administrative SQLite data, builds driving graph tiles with two threads, and creates a checksummed tar bundle/manifest. Build uses the host's memory; no graph generation happens on the live VM. `--package-only` is for an already completed graph, not a replacement for building it. Never keep graph bundles, source downloads, environments or private route inputs in Git.

Timezone polygons are taken from timezone-boundary-builder 2026d and clipped to 33E..37E / 28N..35N, covering the regional extract. Administrative data comes from the same PBF. Elevation, public transit and live traffic are outside this driving deployment. The importer reports two unparseable and five unsupported OSM time-condition expressions; those source restrictions need follow-up if relevant to a destination.

## Install matching runtime on Ubuntu

Create `/home/ubuntu/valhalla-runtime` with `python3 -m venv`, then install `pyvalhalla==3.9.1` from a binary wheel using that environment. Keep it separate from the existing backend environment. Transfer the bundle into a versioned directory under `/home/ubuntu/valhalla-israel/`, compare the archive SHA-256 to the build output, extract, and verify every manifest entry before changing the `current` symlink. The service rechecks graph hashes/version on startup. Preserve the previous directory until validation passes.

Install `valhalla-israel.service` into `/etc/systemd/system/`, run daemon-reload and enable/start. The service uses ubuntu, read-only filesystem protection, 32MiB hard LRU tile cache, released algorithm reservations, one CPU, MemoryHigh192MiB/MemoryMax256MiB and up to128MiB swap. These are trial limits, not a memory usage guarantee; an OOM restart is a failed capacity test. They may need adjustment after measurement.

```bash
curl http://127.0.0.1:8002/status
/home/ubuntu/valhalla-runtime/bin/python valhalla/smoke.py
sudo systemctl show valhalla-israel -p MemoryCurrent -p MemoryPeak -p MemorySwapCurrent -p NRestarts
```

POST `/route`, `/sources_to_targets` (native Actor.matrix), or `/locate`. Car routing only; max22 points per list and484 matrix pairs; max128KiB body. Requests queue and run sequentially. Shortest-distance testing uses `shortest=true` and `disable_hierarchy_pruning=true`; hard exclusions are explicitly enabled. Do not silently relax unpaved/ferry/toll policy. Current failed trip also failed on the public demo when unpaved roads were excluded. Successful routing can snap hundreds of metres from a destination, so arrival needs validation.

Rollback: stop/disable only `valhalla-israel`; existing Trip Planner/Routino and Hermes services are untouched. To update maps, rebuild elsewhere, deploy a new verified directory, change `current`, restart and rerun checks. No database migration or APK reinstall required for this deployment.

## Attribution and licences

Valhalla is MIT-licensed: https://github.com/valhalla/valhalla/blob/3.9.1/COPYING . OpenStreetMap data © OpenStreetMap contributors, ODbL: https://www.openstreetmap.org/copyright . Regional source: https://download.geofabrik.de/asia/israel-and-palestine.html . Timezone geometry: https://github.com/evansiroky/timezone-boundary-builder/releases/tag/2026d (ODbL); IANA timezone rules are included with the engine. Preserve these notices when redistributing the graph. Reproducible source/config/version are retained in build scripts and manifest.

## Production adapter and hard computation deadline
The backend Valhalla adapter uses sequential directed pair routes with the same shortest-distance profile for both the optimization matrix and route geometry. It retains only distances for matrix entries and recalculates selected geometries; identical coordinate pairs are reused. This avoids the native large-matrix workload that exceeded90s on this VM. No automatic Routino fallback or road-policy relaxation.

The service now uses a single persistent native worker behind its synchronous listener. A10second per-call deadline terminates an overlong worker; the following request starts a new worker. Native timeout/recovery is checked with `check_worker.py`. Overall backend provider budget65s remains below web/Android request timeouts. HTTP engine errors and disconnected routes remain visible as failures.

After validation, install `trip-planner-valhalla.conf` under `/etc/systemd/system/trip-planner.service.d/valhalla.conf`, reload systemd and restart both routing service and Trip Planner. The existing startup script honors explicit ROUTING_PROVIDER; its default remains Routino. To roll back, remove only this drop-in and restart Trip Planner; keep original Routino files. Trips, endpoints, arrival overrides, manual ordering, saved routes, link resolution and APK storage need no migration. Cached old routes remain visible until recalculated; new responses identify provider valhalla.

Production unpaved-road setting: `VALHALLA_ALLOW_UNPAVED=true` in the provider drop-in explicitly allows unpaved roads for all clients, including previously installed versions. The adapter preserves other road policies. Logs retain submitted road policy and effective replay payload. New web/iOS requests set avoidUnpaved=false. No app data migration or Android APK update required. Turning this flag off restores each client's submitted policy.

### Long-distance search tuning
Production pair routes now enable road hierarchy pruning (`shortest=true`, `disable_hierarchy_pruning=false`) for both matrix construction and selected-leg geometry. This preserves a distance objective but does not guarantee the mathematically shortest road path. User accepted this speed tradeoff after a Waze-imported long-distance trip hit the old10second deadline. Native call limit is20s, backend HTTP25s and total provider75s; existing clients allow90s reads. Profile flags are recorded in request diagnostics. The older comparison tool still uses hierarchy-disabled exact-search settings for explicit experiments; it is not the production profile. Native worker recovery and road policies remain active.
