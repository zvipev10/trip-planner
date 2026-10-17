#!/usr/bin/env bash
# Build only in the project directory. No sudo, system installs or service changes.
set -euo pipefail
ROUTINO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
ROUTINO_RELEASE=3.4.4
ROUTINO_SHA256=a7017ff04313fa4fb53b995de50feda39ea5e7867bb40a3f9c886187af702830
mkdir -p "$ROUTINO_ROOT/vendor" "$ROUTINO_ROOT/data/israel" "$ROUTINO_ROOT/runs"
if [[ ! -f "$ROUTINO_ROOT/vendor/routino-$ROUTINO_RELEASE.tgz" ]]; then
    curl --fail --location --max-time 120 "https://www.routino.org/download/routino-$ROUTINO_RELEASE.tgz" -o "$ROUTINO_ROOT/vendor/routino-$ROUTINO_RELEASE.tgz"
fi
printf '%s  %s\n' "$ROUTINO_SHA256" "$ROUTINO_ROOT/vendor/routino-$ROUTINO_RELEASE.tgz" | sha256sum --check
if [[ ! -d "$ROUTINO_ROOT/vendor/routino-$ROUTINO_RELEASE" ]]; then
    tar -xzf "$ROUTINO_ROOT/vendor/routino-$ROUTINO_RELEASE.tgz" -C "$ROUTINO_ROOT/vendor"
fi
# bzip2 is unnecessary for .pbf inputs; this avoids an extra development library.
python3 - "$ROUTINO_ROOT/vendor/routino-$ROUTINO_RELEASE/Makefile.conf" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
s = p.read_text().replace('  CFLAGS+=-DUSE_BZIP2', '#  CFLAGS+=-DUSE_BZIP2').replace('  LDFLAGS+=-lbz2', '#  LDFLAGS+=-lbz2')
p.write_text(s)
PY
make -C "$ROUTINO_ROOT/vendor/routino-$ROUTINO_RELEASE/src" -j1 planetsplitter-slim router-slim
if [[ "${1:-}" == "--build-only" ]]; then exit 0; fi
if [[ ! -f "$ROUTINO_ROOT/data/israel-and-palestine.osm.pbf" ]]; then
    curl --fail --location --max-time 300 https://download.geofabrik.de/asia/israel-and-palestine-latest.osm.pbf -o "$ROUTINO_ROOT/data/israel-and-palestine.osm.pbf"
fi
python3 "$ROUTINO_ROOT/scripts/measure.py" \
    --result "$ROUTINO_ROOT/runs/israel-import.json" \
    --log "$ROUTINO_ROOT/runs/israel-import.log" \
    --watch-dir "$ROUTINO_ROOT/data/israel" --memory-mib 512 -- \
    "$ROUTINO_ROOT/vendor/routino-$ROUTINO_RELEASE/src/planetsplitter-slim" \
    "--dir=$ROUTINO_ROOT/data/israel" \
    "--tagging=$ROUTINO_ROOT/vendor/routino-$ROUTINO_RELEASE/xml/routino-tagging.xml" \
    --sort-ram-size=64 --sort-threads=1 --loggable --logtime \
    "$ROUTINO_ROOT/data/israel-and-palestine.osm.pbf"
