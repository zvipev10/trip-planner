"""One-off ordered-route evaluation; never changes the live routing provider.

Use the backend virtualenv. Input is a RouteRequest JSON exported from the
planning_diagnostic request payload. Keep location files outside the repository.
"""
import argparse
import json
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.models import RouteRequest


def build_payload(route, allow_unpaved=False):
    policy = route.road_policy
    return {
        "locations": [{"lat": p.latitude, "lon": p.longitude, "type": "break"} for p in route.points],
        "costing": "auto",
        "costing_options": {"auto": {
            "shortest": True,
            "disable_hierarchy_pruning": True,
            "exclude_unpaved": policy.avoid_unpaved and not allow_unpaved,
            "exclude_ferries": policy.avoid_ferries,
            "exclude_tolls": policy.avoid_tolls,
        }},
        "units": "kilometers",
        "shape_format": "geojson",
    }


def main():
    parser = argparse.ArgumentParser(description="Compare one fixed-order trip with Valhalla. No stop optimization or production fallback.")
    parser.add_argument("input", help="Private RouteRequest JSON path, or - for stdin")
    parser.add_argument("--base-url", required=True, help="Explicit evaluation endpoint; demo usage must remain low-volume")
    parser.add_argument("--allow-unpaved", action="store_true", help="Explicitly relax only the unpaved-road restriction for this trial")
    args = parser.parse_args()
    endpoint = urlparse(args.base_url)
    if endpoint.scheme not in {"http", "https"} or not endpoint.hostname or endpoint.username or endpoint.password or endpoint.query or endpoint.fragment:
        parser.error("Use an HTTP(S) endpoint without embedded credentials, query or fragment")
    raw = sys.stdin.read() if args.input == "-" else Path(args.input).read_text(encoding="utf-8")
    try:
        route = RouteRequest.model_validate_json(raw)
    except ValueError:
        parser.error("Input must be a valid RouteRequest JSON payload")
    body = build_payload(route, args.allow_unpaved)
    request = Request(args.base_url.rstrip("/") + "/route", data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "X-Client-Id": "trip-planner-evaluation", "User-Agent": "TripPlanner/experimental-comparison"})
    try:
        with urlopen(request, timeout=45) as response:
            result = json.load(response)
        trip = result.get("trip", {})
        if trip.get("status") != 0 or len(trip.get("legs", [])) != len(route.points) - 1:
            raise ValueError("Unexpected route response or leg count")
        # Geometry is included for inspecting actual road endpoints rather than
        # assuming the engine reached the submitted pin. Never auto-save it.
        print(json.dumps({"engine": "valhalla-experiment", "orderedOnly": True, "allowUnpavedOverride": args.allow_unpaved, "requestedLocations": body["locations"], "warnings": result.get("warnings", []), "trip": trip}, ensure_ascii=False))
    except HTTPError as error:
        print(json.dumps({"httpStatus": error.code, "body": error.read(8192).decode(errors="replace")}), file=sys.stderr)
        return 1
    except (URLError, TimeoutError, ValueError) as error:
        print(f"Valhalla comparison failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
