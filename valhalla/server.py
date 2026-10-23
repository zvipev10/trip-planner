"""Local-only, single-request Valhalla service for constrained hosts."""
import argparse
import hashlib
from importlib.metadata import version
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path

MAX_BODY = 131072


def runtime_config(data_dir):
    from valhalla import get_config
    root = Path(data_dir).resolve(strict=True)
    config = get_config(tile_dir=root / "tiles", tile_extract="", verbose=False)
    config["mjolnir"].update({"admin": str(root / "admins.sqlite"), "timezone": str(root / "timezones.sqlite"), "traffic_extract": "", "max_cache_size": 33554432, "use_lru_mem_cache": True, "lru_mem_cache_hard_control": True, "concurrency": 1})
    config["thor"].update({"clear_reserved_memory": True, "max_reserved_labels_count_astar": 50000, "max_reserved_labels_count_bidir_astar": 50000})
    config["service_limits"]["auto"].update({"max_locations": 22, "max_matrix_location_pairs": 484, "max_distance": 1000000, "max_matrix_distance": 600000})
    config["service_limits"].update({"allow_hard_exclusions": True, "max_distance_disable_hierarchy_culling": 600000})
    return config


def validate_request(action, body):
    if not isinstance(body, dict) or body.get("costing", "auto") != "auto":
        raise ValueError("Only car routing is enabled")
    keys = ("sources", "targets") if action == "sources_to_targets" else ("locations",)
    for key in keys:
        points = body.get(key)
        if not isinstance(points, list) or not 1 <= len(points) <= 22:
            raise ValueError("Use between 1 and 22 points per list")
    return body


def verify_data(root):
    if version("pyvalhalla") != "3.9.1":
        raise ValueError("Runtime must match the 3.9.1 graph build")
    manifest = json.loads((root / "manifest.json").read_text())
    for name, expected in manifest["files"].items():
        path = (root / name).resolve(strict=True)
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise ValueError("Invalid manifest path")
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for block in iter(lambda: source.read(1048576), b""):
                digest.update(block)
        if digest.hexdigest() != expected["sha256"] or path.stat().st_size != expected["bytes"]:
            raise ValueError("Routing data checksum mismatch")
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--port", type=int, default=8002)
    args = parser.parse_args()
    from valhalla import Actor, ValhallaError
    manifest = verify_data(Path(args.data_dir))
    actor = Actor(runtime_config(args.data_dir))

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(30)

        def send_json(self, status, value):
            data = json.dumps(value, separators=(",", ":")).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path != "/status":
                return self.send_json(404, {"error": "Not found"})
            self.send_json(200, {"status": "ready", "engine": "valhalla", "version": "3.9.1", "concurrency": 1, "source": manifest["source"]})

        def do_POST(self):
            action = self.path.lstrip("/")
            if action not in {"route", "sources_to_targets", "locate"}:
                return self.send_json(404, {"error": "Not found"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= MAX_BODY:
                    return self.send_json(413, {"error": "Invalid request size"})
                body = validate_request(action, json.loads(self.rfile.read(size)))
                result = getattr(actor, "matrix" if action == "sources_to_targets" else action)(body)
                self.send_json(200, json.loads(result) if isinstance(result, str) else result)
            except ValhallaError as error:
                self.send_json(error.http_code, {"error_code": error.code, "error": error.message})
            except (ValueError, TypeError):
                self.send_json(400, {"error": "Invalid routing request"})
            except Exception:
                self.send_json(500, {"error": "Routing service failed"})

    # HTTPServer is deliberately synchronous: Actor never receives concurrent calls.
    server = HTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Valhalla ready on 127.0.0.1:{args.port}; one request at a time", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
