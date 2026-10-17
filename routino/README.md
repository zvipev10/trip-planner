# Low-memory Routino prototype

Routino 3.4.4 slim, OpenStreetMap data via Geofabrik's Israel-and-Palestine extract,
and a curated distance-car profile. There is no paid routing service or API key.
No installation or changes have been made on the user's Ubuntu VM.

## Recorded result

The regional database is 72.57 MiB. Import peaked at 109.33 MiB RSS and about
480 MiB observed temporary database files. Four sample pairs succeeded under a
128 MiB address-space limit, using 10–24.5 MiB peak routing RSS. The complete
backend optimized 20 local Tel Aviv stops in approximately 5 seconds on the
managed development machine; see ../reports/routino-validation.md for limits.
These are not capacity guarantees for the user's 2-vCPU VM.

## Prepare

Requires a C compiler, make, Python 3, curl, tar and zlib development headers.
This script does not install missing OS dependencies or alter system services.

```bash
bash routino/scripts/prepare.sh
```

It downloads and checksum-verifies the pinned source release, builds the two
slim executables serially, downloads regional road data, and imports with a 64 MiB
sorting budget. Prefer preparing data away from a memory-constrained live server.
The 512 MiB importer limit is virtual address space, not total host memory.
Do not rebuild a database while it is being served; prepare a separate directory
and switch only after validation. The script is for initial preparation.

A prepared transfer bundle includes the database. On Ubuntu, compile matching
3.4.4 executables with `bash routino/scripts/prepare.sh --build-only`; do not copy
the Debian-built executables because libc versions may differ. Use the same
Routino version and architecture for the database and executable.

## Backend

From the project root:

```bash
python3 -m venv .venv
.venv/bin/pip install -e './backend[test]'
bash routino/scripts/serve.sh
```

The server binds to localhost only, uses one worker and limits concurrency. No
public hosting, TLS or persistent service configuration is included. Test the
VM's memory/swap and response times before increasing concurrency or exposing it.
On a 1 GiB host, avoid retaining build tools/downloads unnecessarily, but inspect
existing usage before removing anything. Existing Hermes services are untouched.

`ROUTINO_BINARY`, `ROUTINO_DATABASE`, `ROUTINO_PROFILES`, and
`ROUTINO_TRANSLATIONS` can also be set manually with `ROUTING_PROVIDER=routino`.
The bundled profile allows toll roads, excludes ferries and unpaved roads, and
excludes tracks/paths. Other road preferences are rejected, never ignored.
Eligible road classes have equal preference and non-access properties are
neutral, avoiding the default profile's distance weighting. One-way and turn
restrictions are enabled. This is routing on the imported OSM graph, not live
closure/access-condition data or a guarantee of all real-world road restrictions.

The subprocess adapter builds a directed distance matrix sequentially and
recalculates only selected legs for geometry. It avoids caching geometry for
all pairs. CLI distances have 10-meter cumulative precision; stop ordering is
optimized against those rounded values. Point snapping/entrance selection still
needs product validation; this is not ready for unrestricted public use.

## Benchmarks and tests

```bash
python3 routino/scripts/benchmark_routes.py
.venv/bin/python routino/scripts/benchmark_planner.py
cd backend
../.venv/bin/pytest -q
```

The optional real-binary test uses the synthetic fixture graph, built with:

```bash
mkdir -p routino/data/fixture
routino/vendor/routino-3.4.4/src/planetsplitter-slim \
  --dir=routino/data/fixture \
  --tagging=routino/vendor/routino-3.4.4/xml/routino-tagging.xml \
  --sort-ram-size=32 --sort-threads=1 --prune-none \
  routino/fixtures/distance-vs-speed.osm
```

Routino is AGPL-3.0-or-later; retain its notices and meet source-availability
requirements when distributing it or offering modified versions over a network.
OSM data and derived databases require ODbL compliance and OpenStreetMap
attribution. Open-source routing does not provide a map tile or geocoding service;
those remain separate decisions. No public OSM service is used as a free backend.
