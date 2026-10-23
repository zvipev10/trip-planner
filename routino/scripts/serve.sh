#!/usr/bin/env bash
set -euo pipefail
TRIP_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
export ROUTING_PROVIDER="${ROUTING_PROVIDER:-routino}"
export ROUTINO_BINARY="$TRIP_ROOT/routino/vendor/routino-3.4.4/src/router-slim"
export ROUTINO_DATABASE="$TRIP_ROOT/routino/data/israel"
export ROUTINO_PROFILES="$TRIP_ROOT/routino/profiles/distance-car.xml"
export ROUTINO_TRANSLATIONS="$TRIP_ROOT/routino/vendor/routino-3.4.4/xml/routino-translations.xml"
cd "$TRIP_ROOT/backend"
exec "$TRIP_ROOT/.venv/bin/uvicorn" app.main:app --host 127.0.0.1 --port 8000 --workers 1 --limit-concurrency 2
