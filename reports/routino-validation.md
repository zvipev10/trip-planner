# Routino evaluation — 2026-10-17

## Conclusion

Routino slim is a plausible fit for the user's existing 2-vCPU, 952 MiB Ubuntu VM
with 276 MiB available memory and 8.7 GiB free disk. Local measurements are far
below the earlier GraphHopper estimates. Actual VM validation is still required;
no SSH session, install, service change, or benchmark ran on that VM in this task.

## Environment and inputs

- Managed development environment: x86-64, effective 4-CPU quota, 16 GiB RAM limit.
- Routino 3.4.4, compiled from upstream source using GCC, slim executables.
- Source SHA-256: a7017ff04313fa4fb53b995de50feda39ea5e7867bb40a3f9c886187af702830
- Geofabrik Israel-and-Palestine latest extract, downloaded 2026-10-17, about 115 MiB.
- Extract SHA-256: e475ab60193a8da004625da98f42a8064a2e8bba9edf71e23d30f57b72e829de
- Source: https://www.routino.org/download/routino-3.4.4.tgz
- Data: https://download.geofabrik.de/asia/israel-and-palestine.html
- Observations refer to this regional extract, not a custom Israel-only boundary.

## Regional import (executed)

| Metric | Result |
| --- | --- |
| Wall time | 33.24 seconds |
| Importer peak RSS | 109.33 MiB |
| Final database files | 72.57 MiB |
| Peak observed database/temp file size | 480.12 MiB |
| Sorting budget | 64 MiB, one sort thread |
| Process virtual-address limit | 512 MiB |

Peak file usage was sampled every 200 ms during import, so it is an observed
peak, not a hard upper bound. It excludes the input PBF, source and executables.
RSS is from Linux wait4, not complete host memory including file cache.

## Route samples (executed)

Each shortest and quickest sample completed under a 128 MiB virtual-address limit.
Both modes use the curated profile, not the default fastest-navigation profile.
Cumulative CLI distances are rounded to 10 meters.

| Sample | Shortest km | Quickest km | Shortest peak RSS | Shortest wall time |
| --- | --- | --- | --- | --- |
| Tel Aviv local | 3.29 | 3.34 | 10.00 MiB | 0.012 s |
| Tel Aviv–Jerusalem | 62.52 | 64.10 | 22.50 MiB | 0.113 s |
| Haifa local | 8.31 | 8.31 | 11.88 MiB | 0.022 s |
| Beer Sheva–Mitzpe Ramon | 82.77 | 82.77 | 12.38 MiB | 0.022 s |

Largest RSS among all eight samples: 24.50 MiB. Wall times use 10 ms polling and
include launch/output overhead, with warm OS caches. They are not VM predictions,
representative load tests, or validation of every road/access restriction.

## Full backend + optimizer (executed)

Actual road matrices on a local Tel Aviv coordinate grid, with fixed distinct
start/end nodes, one-second OR-Tools search budget, and selected-leg geometry:

| Intermediate stops | Directed matrix calls | Selected geometry calls | Wall time | Backend peak RSS |
| --- | --- | --- | --- | --- |
| 5 | 42 | 6 | 1.410 s | 71.12 MiB |
| 20 | 462 | 21 | 4.988 s | 71.75 MiB |

All intermediate stops appeared exactly once. The 20-stop route was 21.24 km,
using CLI-rounded pair distances. No global optimality claim is made.

The Python benchmark's child-RSS high-water mark was about 72 MiB because forked
children inherit the parent's address space before exec. This is not evidence
that the Routino image itself used 72 MiB; the separate CLI samples above measure
that image without a large parent. Adding the parent/child high-water marks gives
a conservative ~144 MiB process-RSS envelope for these runs, double-counting some
shared pages and excluding host file cache, other services, and concurrent users.
It is not a measured total-memory limit. Start with one backend worker and one
routing subprocess at a time, and measure memory/swap on the actual VM.

## Distance objective and implementation

A synthetic graph with a short slow road and a long fast detour produced:

- Shortest: 0.943 km in detailed section output (0.94 km cumulative CLI output).
- Quickest: 3.169 km in section output (3.17 km cumulative output).

The bundled profile neutralizes preferences among allowed road classes and
non-access properties. Ferries, unpaved roads, tracks and non-car paths are
excluded; one-way and turn restrictions are enabled. Tolls remain allowed.
Unsupported policy combinations return an explicit error. These exclusions define
the eligible graph; the result is not the shortest route over every drivable road.

The backend adapter calls the slim CLI serially without a shell, parses streamed
text geometry, avoids keeping all-pairs geometry in memory, and reports distances
at CLI precision. Google/Waze import resolution, entrance/snapping confirmation,
map rendering, live closures and geocoding remain outside this benchmark.

## Verification

Full backend suite: **35 passed in 3.32 seconds**, one upstream TestClient
deprecation warning. Includes existing tests plus parser validation, unsupported
policy rejection, and a real-binary synthetic shortest-versus-quickest test.
Shell preparation and serving scripts passed `bash -n` syntax checking.

## Recommendation

Proceed to a serial, low-load test on the Ubuntu VM using the prepared database,
without rebuilding it there or disturbing Hermes. Build matching-version binaries
on Ubuntu rather than copying Debian-linked binaries. Keep the API bound to
localhost during evaluation and watch available memory, swap activity and disk.
No paid API or extra VM is needed for this experiment. Public service capacity,
OSM attribution/data licensing, Routino source availability, map tiles and address
search need handling before release; the prototype is not publicly deployed.
