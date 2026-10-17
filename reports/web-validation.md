# Mobile web validation — 2026-10-17

Implemented as static assets inside the existing FastAPI package, at `/web/`.
Relative API URLs preserve the external `/trip-planner/` proxy prefix. HTTP is
intentional for this test deployment. No separate frontend host was created.
Sites' publishing helpers were not available in this environment; the existing
VM/backend deployment is used rather than a second hosted origin/proxy.

## Executed checks

- Python backend suite: **37 passed**, one upstream TestClient deprecation warning.
- Node core suite: **13 passed** (run directly with `node .../core.test.mjs`).
- JavaScript syntax checks passed for the core and browser entrypoint.
- Playwright smoke test passed on installed Chromium, at 390×844 and 1440×1000.
- Browser test used the real local Routino regional database and actual FastAPI
  optimize/calculate endpoints, through a simulated `/trip-planner/` proxy prefix.
- No browser page errors and no horizontal overflow at either tested viewport.

The sample four-location trip optimized to 6.94 km. Intermediate order was:
Northern stop → Midtown stop. The browser then moved Midtown stop earlier,
invalidated the displayed distance, encountered an injected HTTP 503, retried,
and preserved the manual order. Locations survived a reload. Raw summary is in
`reports/web/smoke.json`; generated screenshots are local QA artifacts, not source.

Core tests cover title validation, insecure-context UUID support, distinct and
round-trip endpoint roles, unresolved coordinates, stop limits, manual order
integrity, response validation, stale revisions, shared-link parsing, and backup
validation. Endpoint tests confirm static assets work without a configured
routing provider and the root redirect remains relative for reverse proxies.

## Limits and deployment

This is Chromium testing with a mobile viewport, not a physical iPhone or WebKit
validation. No service worker or native Share Extension is included. Paste links
using ordinary browser editing. Short links/addresses need confirmed coordinates.
The route overview displays returned road geometry without geographic base tiles.

Browser localStorage holds trips per browser/origin; export/import supports
backups. Reload/import clears cached route results for recalculation. Storage
failure preserves the existing saved state. Moving stops hides stale distance.
The VM service has not been modified by this coding environment. Deploy the
committed files/package and restart `trip-planner` as documented in web/README.md.
The intended URL after deployment is:
http://151.145.93.180/trip-planner/web/

The previous direct live API check returned a valid Routino route at the VM's
`/trip-planner/v1/routes/optimize` endpoint. This browser smoke test used the local
engine, not a remote deployed copy of the new web page. Public HTTP API
unauthenticated usage and production capacity remain unchanged by this feature.
