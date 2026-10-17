"""GraphHopper route adapter. Profiles must be configured and validated externally.

Build matrices from directed pair routes to avoid assuming that the hosted Matrix
API supports a custom profile. This is a correctness-first prototype, not a
production-cost recommendation. No speed/distance weighting is invented here.
"""
import math
from time import monotonic
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from .models import Point, RoadPolicy
from .provider import Matrix, PlanningError, RoadRoute


@dataclass(frozen=True)
class Profile:
    name: str
    policy: RoadPolicy


class GraphHopperProvider:
    name = "graphhopper"

    def __init__(self, profiles: list[Profile], api_key: str = "", base_url: str = "https://graphhopper.com/api/1", transport=None):
        parsed = urlparse(base_url)
        if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}):
            raise ValueError("Use HTTPS, or HTTP on a loopback address for a local engine")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Base URL must not contain credentials, query, or fragment")
        self.profiles, self.api_key, self.base_url = profiles, api_key, base_url.rstrip("/")
        self.transport = transport
        # Provider instances are request-scoped. Never share route data across trips.
        self.cache: dict[tuple, RoadRoute | None] = {}
        self.deadline = monotonic() + 60

    def _profile(self, policy: RoadPolicy) -> str:
        for profile in self.profiles:
            if profile.policy == policy:
                return profile.name
        raise PlanningError("unsupported_road_policy", "No validated GraphHopper profile matches these road preferences.")

    def _client(self):
        return httpx.Client(timeout=httpx.Timeout(15, connect=5), transport=self.transport, follow_redirects=False)

    def _leg(self, client, start: Point, end: Point, profile: str) -> RoadRoute | None:
        key = (profile, start.latitude, start.longitude, end.latitude, end.longitude)
        if key in self.cache:
            return self.cache[key]
        if key[1:3] == key[3:5]:
            result = RoadRoute([0], [(start.longitude, start.latitude), (end.longitude, end.latitude)])
            self.cache[key] = result
            return result
        remaining = self.deadline - monotonic()
        if remaining <= 0:
            raise PlanningError("provider_timeout", "Routing exceeded the prototype calculation budget.", 504)
        payload = {"profile": profile, "points": [[start.longitude, start.latitude], [end.longitude, end.latitude]], "points_encoded": False, "instructions": False}
        try:
            response = client.post(self.base_url + "/route", params={"key": self.api_key} if self.api_key else {}, json=payload, timeout=min(15, remaining))
        except httpx.TimeoutException:
            raise PlanningError("provider_timeout", "GraphHopper timed out. Retry the calculation.", 504) from None
        except httpx.HTTPError:
            raise PlanningError("provider_unavailable", "GraphHopper could not be reached.", 502) from None
        # Do not expose upstream error text or URLs: they may contain keys/locations.
        try:
            data = response.json()
        except ValueError:
            raise PlanningError("invalid_provider_response", "GraphHopper returned invalid JSON.", 502) from None
        if response.status_code == 400 and isinstance(data, dict):
            hints = data.get("hints", [])
            if isinstance(hints, list) and any(isinstance(h, dict) and str(h.get("details", "")).endswith("ConnectionNotFoundException") for h in hints):
                self.cache[key] = None
                return None
        if response.status_code == 429:
            raise PlanningError("provider_rate_limited", "GraphHopper request allowance was reached. Retry later.", 503)
        if response.status_code in (401, 403):
            raise PlanningError("provider_authentication_failed", "GraphHopper credentials or profile access need configuration.", 503)
        if not response.is_success:
            raise PlanningError("provider_rejected_request", "GraphHopper rejected the routing request.", 502)
        try:
            path = data["paths"][0]
            distance = path["distance"]
            coordinates = path["points"]["coordinates"]
            if isinstance(distance, bool) or not isinstance(distance, (int, float)) or not math.isfinite(distance) or not 0 <= distance <= 10**12:
                raise ValueError()
            if path["points"].get("type") != "LineString" or len(coordinates) < 2:
                raise ValueError()
            for coordinate in coordinates:
                if len(coordinate) != 2 or any(isinstance(c, bool) or not isinstance(c, (float, int)) or not math.isfinite(c) for c in coordinate):
                    raise ValueError()
                if not (-180 <= coordinate[0] <= 180 and -90 <= coordinate[1] <= 90):
                    raise ValueError()
            result = RoadRoute([round(distance)], [tuple(c) for c in coordinates])
        except (KeyError, IndexError, TypeError, ValueError):
            raise PlanningError("invalid_provider_response", "GraphHopper returned invalid distance or geometry.", 502) from None
        self.cache[key] = result
        return result

    def distance_matrix(self, points: list[Point], policy: RoadPolicy) -> Matrix:
        profile = self._profile(policy)
        matrix: Matrix = [[0 for _ in points] for _ in points]
        with self._client() as client:
            for i, start in enumerate(points):
                for j, end in enumerate(points):
                    if i != j:
                        route = self._leg(client, start, end, profile)
                        matrix[i][j] = route.leg_distances[0] if route else None
        return matrix

    def route(self, ordered_points: list[Point], policy: RoadPolicy) -> RoadRoute:
        profile = self._profile(policy)
        distances, coordinates = [], []
        with self._client() as client:
            for start, end in zip(ordered_points, ordered_points[1:]):
                leg = self._leg(client, start, end, profile)
                if leg is None:
                    raise PlanningError("unreachable_leg", "No car route connects these consecutive locations.", location_ids=[start.id, end.id])
                distances.extend(leg.leg_distances)
                # Keep both geometries if snapping gives different endpoints.
                coordinates.extend(leg.coordinates[1:] if coordinates and coordinates[-1] == leg.coordinates[0] else leg.coordinates)
        return RoadRoute(distances, coordinates)
