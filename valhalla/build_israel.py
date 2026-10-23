"""Prepare a checksummed, portable Israel driving graph away from the live VM.
Requires the pinned build environment on Windows. Never alters server services.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import urllib.request
import valhalla
from valhalla import get_config


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--package-only", action="store_true", help="Package an already completed graph in the work directory")
    args = parser.parse_args()
    if os.name != "nt":
        parser.error("This build recipe uses the pinned Windows build environment")
    root = Path(args.work_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    tiles = root / "tiles"
    tiles.mkdir(exist_ok=True)
    url = "https://download.geofabrik.de/asia/israel-and-palestine-261021.osm.pbf"
    pbf = root / "israel-and-palestine-261021.osm.pbf"
    if not pbf.exists():
        urllib.request.urlretrieve(url, pbf)
    expected = urllib.request.urlopen(url + ".md5", timeout=60).read().decode().split()[0]
    assert hashlib.md5(pbf.read_bytes()).hexdigest() == expected, "Source checksum mismatch"
    source = {"url": url, "md5": expected, "sha256": digest(pbf), "bytes": pbf.stat().st_size, "pyvalhalla": "3.9.1"}
    config = get_config(tile_dir=tiles, tile_extract="", verbose=True)
    config["mjolnir"].update({"concurrency": 2, "include_bicycle": False, "include_pedestrian": False, "admin": str(root / "admins.sqlite"), "timezone": str(root / "timezones.sqlite")})
    config["logging"].update({"type": "std_out", "color": False})
    (root / "build.json").write_text(json.dumps(config, indent=2))
    env = dict(os.environ)
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + str(Path(valhalla.__file__).parent / "bin") + os.pathsep + env["PATH"]
    if not (root / "timezones.sqlite").exists():
        subprocess.run([sys.executable, str(Path(__file__).with_name("build_timezones_windows.py")), str(root)], check=True, env=env)
    for command, label in ([] if args.package_only else [("valhalla_build_admins", "admins"), ("valhalla_build_tiles", "tiles")]):
        with (root / (label + "-rebuild.log")).open("w") as output:
            subprocess.run([sys.executable, "-m", "valhalla", command, "-c", str(root / "build.json"), str(pbf)], check=True, env=env, stdout=output, stderr=subprocess.STDOUT)
    files = sorted(tiles.rglob("*.gph")) + [root / "admins.sqlite", root / "timezones.sqlite"]
    assert files and any(p.suffix == ".gph" for p in files), "No graph tiles"
    manifest = {"source": source, "builtUtc": datetime.now(timezone.utc).isoformat(), "timezoneSource": "timezone-boundary-builder/2026d, clipped to 33E..37E / 28N..35N", "mode": "driving", "files": {p.relative_to(root).as_posix(): {"bytes": p.stat().st_size, "sha256": digest(p)} for p in files}}
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2))
    bundle = root / "israel-valhalla-3.9.1-20261021.tar.gz"
    with tarfile.open(bundle, "w:gz") as archive:
        for p in files + [root / "manifest.json"]:
            archive.add(p, arcname=p.relative_to(root).as_posix())
    print(json.dumps({"bundle": str(bundle), "bytes": bundle.stat().st_size, "sha256": digest(bundle), "tileCount": len(files) - 2}))


if __name__ == "__main__":
    main()
