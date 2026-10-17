from itertools import permutations

import pytest
from fastapi.testclient import TestClient

from app.main import app, get_provider
from app.provider import RoadRoute
from app.solver import optimize

# Synthetic directed distances, NOT measurements of Israeli roads.
MATRIX = [[0, 40, 10, 100], [30, 0, 50, 10], [20, 10, 0, 60], [90, 70, 80, 0]]


def cost(matrix, order):
    return sum(matrix[a][b] for a, b in zip(order, order[1:]))


class FixtureProvider:
    name = "synthetic-test-fixture"

    def distance_matrix(self, points, policy):
        return MATRIX

    def route(self, points, policy):
        index = {"start": 0, "a": 1, "b": 2, "end": 3}
        order = [index[p.id] for p in points]
        return RoadRoute([MATRIX[a][b] for a, b in zip(order, order[1:])], [(p.longitude, p.latitude) for p in points])


@pytest.fixture
def client():
    app.dependency_overrides[get_provider] = FixtureProvider
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def payload():
    return {"revision": 7, "start": {"id": "start", "latitude": 32.08, "longitude": 34.78}, "end": {"id": "end", "latitude": 31.77, "longitude": 35.21}, "stops": [{"id": "a", "latitude": 31.89, "longitude": 34.81}, {"id": "b", "latitude": 31.97, "longitude": 34.79}]}


def test_solver_matches_exhaustive_search():
    route = optimize(MATRIX, 40)
    best = min(cost(MATRIX, [0, *p, 3]) for p in permutations([1, 2]))
    assert route[0] == 0 and route[-1] == 3
    assert sorted(route) == list(range(4))
    assert cost(MATRIX, route) == best


def test_optimize(client, payload):
    response = client.post("/v1/routes/optimize", json=payload)
    assert response.status_code == 200
    result = response.json()
    assert result["orderedStopIds"] == ["b", "a"]
    assert result["distanceMeters"] == 30
    assert result["revision"] == 7
    assert result["geometry"]["coordinates"][0] == [34.78, 32.08]


def test_manual_order(client, payload):
    response = client.post("/v1/routes/calculate", json=payload)
    assert response.status_code == 200
    assert response.json()["orderedStopIds"] == ["a", "b"]
    assert response.json()["distanceMeters"] == 150


def test_round_trip(client, payload):
    payload["end"].update(latitude=payload["start"]["latitude"], longitude=payload["start"]["longitude"])
    assert client.post("/v1/routes/optimize", json=payload).status_code == 200


def test_duplicate_ids(client, payload):
    payload["end"]["id"] = "start"
    assert client.post("/v1/routes/optimize", json=payload).status_code == 422


def test_stop_limit(client, payload):
    payload["stops"] = [{"id": str(i), "latitude": 32, "longitude": 35} for i in range(21)]
    assert client.post("/v1/routes/optimize", json=payload).status_code == 422


def test_unreachable_node():
    from app.provider import PlanningError
    with pytest.raises(PlanningError, match="No complete route"):
        optimize([[0, None, 10], [None, 0, None], [10, None, 0]], 40)


def test_forbidden_arc_is_never_used():
    matrix = [[0, None, 1, 10], [1, 0, 1, 1], [1, 1, 0, 1], [1, 1, 1, 0]]
    assert optimize(matrix, 40) == [0, 2, 1, 3]


def test_no_intermediate_stops():
    assert optimize([[0, 5], [7, 0]], 40) == [0, 1]


def test_profile_mismatch(client, payload):
    class BadProvider(FixtureProvider):
        def route(self, points, policy):
            route = super().route(points, policy)
            route.leg_distances[0] += 100
            return route
    app.dependency_overrides[get_provider] = BadProvider
    response = client.post("/v1/routes/optimize", json=payload)
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "routing_profile_mismatch"


def test_unconfigured_service(payload):
    with TestClient(app) as client:
        response = client.post("/v1/routes/optimize", json=payload)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "provider_not_configured"
