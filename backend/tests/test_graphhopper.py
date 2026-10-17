import httpx
import pytest

from app.config import configured_provider
from app.graphhopper import GraphHopperProvider, Profile
from app.models import Point, RoadPolicy
from app.provider import PlanningError

POLICY = RoadPolicy()
POINTS = [Point(id="a", latitude=32.08, longitude=34.78), Point(id="b", latitude=31.77, longitude=35.21)]


def provider(handler):
    return GraphHopperProvider([Profile("distance-car", POLICY)], api_key="test-key", transport=httpx.MockTransport(handler))


def response(distance=123.4, coords=None):
    return {"paths": [{"distance": distance, "points": {"type": "LineString", "coordinates": coords or [[34.78, 32.08], [35.21, 31.77]]}}]}


def test_request_contract_directed_matrix_and_cache():
    import json
    calls = []
    def handle(request):
        payload = json.loads(request.content)
        calls.append(payload)
        assert request.method == "POST"
        assert request.url.path == "/api/1/route"
        assert request.url.params["key"] == "test-key"
        assert payload["profile"] == "distance-car"
        assert payload["points_encoded"] is False
        forward = payload["points"][0] == [34.78, 32.08]
        return httpx.Response(200, json=response(123.4 if forward else 456.7, payload["points"]))
    engine = provider(handle)
    assert engine.distance_matrix(POINTS, POLICY) == [[0, 123], [457, 0]]
    assert engine.route(POINTS, POLICY).leg_distances == [123]
    assert len(calls) == 2
    assert calls[0]["points"] == [[34.78, 32.08], [35.21, 31.77]]


def test_no_silent_policy_fallback():
    engine = provider(lambda request: pytest.fail("Unsupported policy must not call provider"))
    with pytest.raises(PlanningError) as exc:
        engine.distance_matrix(POINTS, RoadPolicy(avoidTolls=True))
    assert exc.value.code == "unsupported_road_policy"


def test_unreachable_pair():
    engine = provider(lambda request: httpx.Response(400, json={"hints": [{"details": "com.graphhopper.util.exceptions.ConnectionNotFoundException"}]}))
    assert engine.distance_matrix(POINTS, POLICY) == [[0, None], [None, 0]]
    with pytest.raises(PlanningError) as exc:
        engine.route(POINTS, POLICY)
    assert exc.value.location_ids == ["a", "b"]


@pytest.mark.parametrize("status,code", [(401, "provider_authentication_failed"), (403, "provider_authentication_failed"), (429, "provider_rate_limited"), (500, "provider_rejected_request")])
def test_upstream_errors_are_sanitized(status, code):
    engine = provider(lambda request: httpx.Response(status, json={"message": "secret-key-and-private-location"}))
    with pytest.raises(PlanningError) as exc:
        engine.route(POINTS, POLICY)
    assert exc.value.code == code
    assert "secret-key" not in str(exc.value)


def test_timeout():
    def handle(request):
        raise httpx.ReadTimeout("contains sensitive URL")
    with pytest.raises(PlanningError) as exc:
        provider(handle).route(POINTS, POLICY)
    assert exc.value.code == "provider_timeout"


@pytest.mark.parametrize("data", [{}, {"paths": []}, response(-1), response(True), response(coords=[[999, 32], [35, 31]])])
def test_malformed_success_response(data):
    with pytest.raises(PlanningError) as exc:
        provider(lambda request: httpx.Response(200, json=data)).route(POINTS, POLICY)
    assert exc.value.code == "invalid_provider_response"


def test_same_coordinate_endpoints():
    end = POINTS[0].model_copy(update={"id": "end"})
    engine = provider(lambda request: pytest.fail("No request needed for identical coordinates"))
    assert engine.route([POINTS[0], end], POLICY).leg_distances == [0]


def test_configuration_requires_validation(monkeypatch):
    monkeypatch.setenv("ROUTING_PROVIDER", "graphhopper")
    monkeypatch.delenv("GRAPHHOPPER_DISTANCE_VALIDATED", raising=False)
    with pytest.raises(PlanningError) as exc:
        configured_provider()
    assert exc.value.code == "distance_profile_unvalidated"


def test_configured_profile(monkeypatch):
    monkeypatch.setenv("ROUTING_PROVIDER", "graphhopper")
    monkeypatch.setenv("GRAPHHOPPER_DISTANCE_VALIDATED", "true")
    monkeypatch.setenv("GRAPHHOPPER_PROFILES_JSON", '[{"name":"my-profile","roadPolicy":{"avoidTolls":false,"avoidFerries":true,"avoidUnpaved":true}}]')
    assert configured_provider()._profile(POLICY) == "my-profile"


def test_total_budget():
    engine = provider(lambda request: pytest.fail("Budget must expire before request"))
    engine.deadline = 0
    with pytest.raises(PlanningError) as exc:
        engine.route(POINTS, POLICY)
    assert exc.value.status == 504
