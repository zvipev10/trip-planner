# Prototype validation — 2026-10-17

## Executed results

Python 3.12.14; OR-Tools 9.15.6755. Dependency versions are recorded in
`backend/requirements.lock` (Linux/Python 3.12 environment snapshot).

- API and solver tests: **11 passed in 3.33 seconds**.
- The sandbox's network restriction caused Starlette TestClient to hang during
  event-loop startup. Running the suite with network permission passed. The tests
  use only in-process synthetic providers; no remote routing API is called.
- One upstream deprecation warning: Starlette currently recommends httpx2 for
  its TestClient. Existing httpx tests pass; no application defect observed.

Synthetic benchmark, solver budget 250 ms per case:

| Intermediate stops | Solver seconds | Every stop exactly once | Matches exhaustive optimum |
| --- | --- | --- | --- |
| 0 | 0.0032 | Yes | Yes |
| 2 | 0.2505 | Yes | Yes |
| 5 | 0.2508 | Yes | Yes |
| 10 | 0.2508 | Yes | Not checked |
| 20 | 0.2510 | Yes | Not checked |

These are deterministic randomly generated directed matrices, not road distances.
They validate solver plumbing and bounded runtime on this machine. The runtime
mostly reflects the configured search budget, not a real-trip latency estimate.
No claim of optimality for 10/20 stops or geographic routing correctness follows.

Test coverage: exact comparison on a small matrix; fixed endpoints; directed
forbidden arcs; unreachable mandatory stop; no intermediate stops; round-trip
request handling with equal-coordinate endpoints; manual order preservation;
duplicate IDs; stop limit; matrix/geometry profile disagreement; unconfigured
provider's explicit HTTP 503. Round-trip fixture testing does not validate a real
road loop. No Android implementation or end-to-end device test exists yet.

## Provider findings

Reviewed the official GraphHopper core custom-model documentation:
https://github.com/graphhopper/graphhopper/blob/master/docs/core/custom-models.md

Its documented edge weight is:

```
edge_distance / (speed * priority)
+ edge_distance * distance_influence
+ turn_penalty
```

Increasing `distance_influence` prefers shorter routes, but does not eliminate
the speed/priority/turn terms. Merely setting a large influence does not establish
a pure-distance objective. Therefore GraphHopper remains a candidate requiring
an explicitly validated profile, including matching matrix support. This is a
source/documentation finding, not an executed API test or an exhaustive provider
comparison. Hosted API terms, Israel coverage, limits and prices are unverified.

## Remaining live validation

No routing-provider credentials or outbound identities were configured in the
managed environment. Live Israel routes, Hebrew/English geocoding, link imports,
road closures/access restrictions, response times, billable units and pricing
remain untested. No subscription, deployment or external account was created.
The default API deliberately fails closed for route calculation until a validated
provider is wired in. Next: choose/connect a genuine distance-based provider or
run a configurable road engine, then execute the Israel acceptance checklist in
README.md before Android integration.


## GraphHopper integration update

The request-scoped adapter and environment configuration are implemented in
`app/graphhopper.py` and `app/config.py`. The full suite now passes: **28 tests in
3.36 seconds** (17 new adapter tests plus the existing 11). One upstream TestClient
deprecation warning remains. New tests use HTTP mocks and check POST formatting,
coordinate order, directed distances, request-local caching, forbidden policy
fallback, unreachable connections, sanitized errors, timeouts, malformed responses,
identical endpoints, validation gating, configuration and budget expiry.

This checks application-side behavior against the expected GraphHopper contract;
it is not a live API compatibility test. No real provider calls or costs were
incurred. Pairwise route requests avoid depending on custom Matrix API support,
but can require 462 requests at the proposed limit. Live credentials, actual
profile availability/definition, distance-objective validation and Israel road
benchmarks remain outstanding. GraphHopper remains the selected candidate.
