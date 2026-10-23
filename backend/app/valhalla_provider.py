"""Valhalla distance-first adapter with bounded hierarchy-pruned pair evaluation."""
import math
from time import monotonic
from urllib.parse import urlparse
import httpx
from .diagnostics import event
from .models import Point, RoadPolicy
from .provider import Matrix, PlanningError, RoadRoute


def decode_polyline6(encoded):
    if not isinstance(encoded, str) or len(encoded) > 1000000:
        raise ValueError()
    index, latitude, longitude = 0, 0, 0
    coordinates = []
    while index < len(encoded):
        delta = []
        for _ in range(2):
            value, shift = 0, 0
            while True:
                if index >= len(encoded) or shift > 30:
                    raise ValueError()
                chunk = ord(encoded[index]) - 63
                index += 1
                if not 0 <= chunk <= 63:
                    raise ValueError()
                value |= (chunk & 31) << shift
                shift += 5
                if chunk < 32:
                    break
            delta.append(~(value >> 1) if value & 1 else value >> 1)
        latitude += delta[0]
        longitude += delta[1]
        coordinates.append((longitude / 1000000, latitude / 1000000))
        if len(coordinates) > 50000:
            raise ValueError()
    return coordinates


class ValhallaProvider:
    name = "valhalla"
    diagnostic_profile = {"shortest": False, "useDistance": 1.0, "hierarchyPruning": True}

    def __init__(self, base_url="http://127.0.0.1:8002", transport=None, allow_unpaved=False):
        parsed = urlparse(base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"} or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Valhalla must use the configured local service")
        self.allow_unpaved = allow_unpaved
        self.base_url, self.transport = base_url.rstrip("/"), transport
        self.deadline = monotonic() + 75
        self.distances = {}

    def effective_policy(self, policy):
        return policy.model_copy(update={"avoid_unpaved": False}) if self.allow_unpaved else policy

    @staticmethod
    def _key(start, end, policy):
        return (start.latitude, start.longitude, end.latitude, end.longitude, policy.model_dump_json())

    def _leg(self, client, start, end, policy):
        if start.latitude == end.latitude and start.longitude == end.longitude:
            return RoadRoute([0], [(start.longitude, start.latitude), (end.longitude, end.latitude)])
        remaining = self.deadline - monotonic()
        if remaining <= 0:
            raise PlanningError("provider_timeout", "Routing exceeded its calculation budget.", 504)
        payload = {"locations": [{"lat": p.latitude, "lon": p.longitude, "type": "break"} for p in (start, end)], "costing": "auto", "costing_options": {"auto": {"shortest": False, "use_distance": 1.0, "disable_hierarchy_pruning": False, "exclude_unpaved": policy.avoid_unpaved, "exclude_ferries": policy.avoid_ferries, "exclude_tolls": policy.avoid_tolls}}, "units": "kilometers", "shape_format": "polyline6"}
        try:
            response = client.post(self.base_url + "/route", json=payload, timeout=min(25, remaining))
        except httpx.TimeoutException:
            raise PlanningError("provider_timeout", "Valhalla timed out. Try fewer or closer stops.", 504) from None
        except httpx.HTTPError:
            raise PlanningError("provider_unavailable", "Valhalla could not be reached.", 503) from None
        try:
            data = response.json()
        except ValueError:
            raise PlanningError("invalid_provider_response", "Valhalla returned invalid JSON.", 502) from None
        if not response.is_success:
            code = data.get("error_code") if isinstance(data, dict) else None
            event("valhalla_leg_failed", start=start.model_dump(mode="json"), end=end.model_dump(mode="json"), status=response.status_code, upstreamCode=code)
            if response.status_code == 400 and code in {441, 442}:
                return None
            if response.status_code == 400 and code in {170, 171}:
                raise PlanningError("location_not_routable", "A location has no nearby routable car road.", location_ids=[start.id, end.id])
            if response.status_code == 503:
                raise PlanningError("provider_unavailable", "Valhalla worker is restarting. Please retry.", 503)
            if response.status_code == 504:
                raise PlanningError("provider_timeout", "Valhalla exceeded its per-route calculation budget.", 504)
            raise PlanningError("provider_failed", "Valhalla rejected this route calculation.", 502)
        try:
            trip = data["trip"]
            if trip["status"] != 0 or trip["units"] != "kilometers" or len(trip["legs"]) != 1:
                raise ValueError()
            leg = trip["legs"][0]
            distance = leg["summary"]["length"]
            shape = leg["shape"]
            if isinstance(distance, bool) or not isinstance(distance, (int, float)) or not math.isfinite(distance) or not 0 <= distance <= 10**9:
                raise ValueError()
            if isinstance(shape, str):
                coordinates = decode_polyline6(shape)
            else:
                if shape["type"] != "LineString":
                    raise ValueError()
                coordinates = shape["coordinates"]
            if not 2 <= len(coordinates) <= 50000:
                raise ValueError()
            for coordinate in coordinates:
                if len(coordinate) != 2 or any(isinstance(c, bool) or not isinstance(c, (int, float)) or not math.isfinite(c) for c in coordinate) or not (-180 <= coordinate[0] <= 180 and -90 <= coordinate[1] <= 90):
                    raise ValueError()
            return RoadRoute([round(distance * 1000)], [tuple(c) for c in coordinates])
        except (KeyError, IndexError, TypeError, ValueError):
            raise PlanningError("invalid_provider_response", "Valhalla returned invalid distance or geometry.", 502) from None

    def _client(self):
        return httpx.Client(transport=self.transport, timeout=25, follow_redirects=False, trust_env=False)

    def distance_matrix(self, points: list[Point], policy: RoadPolicy) -> Matrix:
        policy = self.effective_policy(policy)
        matrix = [[0 for _ in points] for _ in points]
        with self._client() as client:
            for i, start in enumerate(points):
                for j, end in enumerate(points):
                    if i == j:
                        continue
                    key = self._key(start, end, policy)
                    if key not in self.distances:
                        leg = self._leg(client, start, end, policy)
                        self.distances[key] = leg.leg_distances[0] if leg else None
                    matrix[i][j] = self.distances[key]
        # Cache only integer distances, not every pair's potentially large geometry.
        return matrix

    def route(self, ordered_points: list[Point], policy: RoadPolicy) -> RoadRoute:
        policy = self.effective_policy(policy)
        distances, coordinates = [], []
        with self._client() as client:
            for start, end in zip(ordered_points, ordered_points[1:]):
                leg = self._leg(client, start, end, policy)
                if leg is None:
                    raise PlanningError("unreachable_leg", "No car route connects these consecutive locations under your road preferences.", location_ids=[start.id, end.id])
                distances.extend(leg.leg_distances)
                coordinates.extend(leg.coordinates[1:] if coordinates and coordinates[-1] == leg.coordinates[0] else leg.coordinates)
        return RoadRoute(distances, coordinates)
