# Trip Planner mobile web

Buildless HTML/CSS/ES modules, served by the existing FastAPI backend. The page
uses the same origin and reverse-proxy prefix as the API. It requires no Node
server, new hosting account, CORS configuration, or paid frontend service.

## Update the existing Ubuntu deployment

The following assumes `/home/ubuntu/trip-planner` is a Git checkout of the project
and that the existing `trip-planner` service uses its `.venv`. If it was installed
from an archive instead, update the same backend source files/package without
replacing the existing service configuration or road database.

```bash
cd /home/ubuntu/trip-planner
git pull --ff-only
.venv/bin/python -m pip install --no-deps -e ./backend
sudo systemctl restart trip-planner
curl -f http://127.0.0.1:8000/web/ -o /dev/null
```

Then open **http://151.145.93.180/trip-planner/web/** in Safari. Include the final
slash. The existing Nginx `/trip-planner/` proxy must forward all paths under that
prefix, including `/web/`, `/web/app.mjs`, `/web/core.mjs`, `/web/style.css` and the
existing `/v1/routes/` API paths. The app computes relative URLs and preserves
the prefix; it does not connect to a different origin or hard-code the VM IP.

No changes were made on the VM by the coding environment; a pull and service
restart are still required. Keep existing database/environment configuration.
If pip metadata points elsewhere, confirm the systemd service's working directory
and interpreter before replacing anything.

## Use on iPhone

1. Create a titled trip (or try the sample Tel Aviv trip).
2. Add locations. Paste a Google Maps/Waze link or enter an address/coordinates.
3. Use Extract coordinates for explicit coordinate queries. Short links and plain
   addresses remain unresolved; confirm both coordinates before calculating.
4. Choose start and end; use the same place for a round trip.
5. Optimize the stop order and inspect approximate driving distance.
6. Move intermediate stops using the up/down buttons, then calculate your order.

The interactive map uses bundled Leaflet 1.9.4 and HTTPS OpenStreetMap tiles,
with actual returned road geometry and labeled start/intermediate/end markers.
Users can pan, zoom, open stop labels, and fit the full route. Changing stop order
hides the old map until recalculation. A tile failure shows a retry message while
the route overlay and stop list remain available. No paid map API key is needed;
tiles require an internet connection. Attribution remains visible on the map.
The added JS/CSS/license assets are included in the backend Python package.

Trips save in localStorage per browser and origin, not on the server. Export JSON
backups to move or recover data. Import explicitly replaces this browser's trips
with confirmation. Storage errors preserve existing saved data and keep an editor
open. Cached route results are cleared after reload/import and must be recalculated.
Clearing Safari website data also removes trips; a different origin (including a
future HTTPS address) has separate storage, so export before switching.

HTTP is intentional for this test endpoint. There is no service worker/offline
PWA or native iOS Share Extension. Paste links using the standard iOS edit menu;
clipboard APIs and native receiving through the Share Sheet are not required.
UUID generation supports insecure HTTP contexts where crypto.randomUUID is absent.

## Verification

```bash
node backend/tests/web/core.test.mjs
cd backend
../.venv/bin/pytest -q
```

The optional browser smoke script uses an installed Chromium and Playwright,
plus a configured local backend at `127.0.0.1:8765` with the real Routino database:

```bash
python backend/tests/web/browser_smoke.py
```

It simulates the `/trip-planner/` proxy prefix, checks a 390px mobile viewport,
real optimization/manual recalculation, an injected 503 with retry, persistence,
and desktop overflow. This is Chromium testing, not physical iPhone/Safari QA.

## Manual arrival points
If a place has no nearby routable road, choose an arrival point from the error panel. Tap the map, drag the arrival marker, or enter coordinates; the original destination remains saved. Confirmation saves the override and recalculates. Reset to original location removes it. A place used for both start and end uses the same override at both ends. Arrival overrides survive browser reload and backup export/import. Access is unverified: select an appropriate entrance or parking area. No automatic suggestions or walking connection are provided.
