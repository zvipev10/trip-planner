from pathlib import Path
import importlib.util
from app.models import RouteRequest

spec = importlib.util.spec_from_file_location("compare_valhalla", Path(__file__).resolve().parents[2] / "tools/compare_valhalla.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_comparison_preserves_policy_endpoints_and_order():
    route = RouteRequest.model_validate({"revision": 0, "start": {"id": "s", "latitude": 32, "longitude": 35}, "end": {"id": "e", "latitude": 32, "longitude": 35}, "stops": [{"id": "a", "latitude": 33, "longitude": 35}], "roadPolicy": {"avoidTolls": True, "avoidUnpaved": True, "avoidFerries": True}})
    payload = module.build_payload(route)
    assert [(p["lat"], p["lon"]) for p in payload["locations"]] == [(32, 35), (33, 35), (32, 35)]
    options = payload["costing_options"]["auto"]
    assert options == {"shortest": True, "disable_hierarchy_pruning": True, "exclude_unpaved": True, "exclude_ferries": True, "exclude_tolls": True}
    relaxed = module.build_payload(route, allow_unpaved=True)["costing_options"]["auto"]
    assert relaxed == {**options, "exclude_unpaved": False}
    assert route.road_policy.avoid_unpaved is True
