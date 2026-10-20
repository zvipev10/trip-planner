"""Low-memory subprocess adapter for the bundled distance-car Routino profile."""
import math
import re
from pathlib import Path
import subprocess
from threading import Lock
from time import monotonic

from .models import Point, RoadPolicy
from .provider import Matrix, PlanningError, RoadRoute

# One routing subprocess at a time in this API worker. Run only one worker on
# low-memory hosts; multiple processes do not share this lock.
_ROUTER_LOCK = Lock()


class RoutinoProvider:
    name = "routino"

    def __init__(self, binary: str, database: str, profiles: str, translations: str):
        self.binary, self.database, self.profiles, self.translations = map(lambda p: str(Path(p).resolve()), (binary, database, profiles, translations))
        if not Path(self.binary).is_file() or not Path(self.database).is_dir() or not Path(self.profiles).is_file() or not Path(self.translations).is_file():
            raise PlanningError("provider_configuration_error", "Routino paths are missing or invalid.", 503)
        self.deadline = monotonic() + 60

    @staticmethod
    def _policy(policy: RoadPolicy):
        if policy != RoadPolicy():
            raise PlanningError("unsupported_road_policy", "This Routino profile supports tolls allowed, ferries avoided, and unpaved roads avoided only.")

    def _leg(self, start: Point, end: Point) -> RoadRoute | None:
        if start.latitude == end.latitude and start.longitude == end.longitude:
            return RoadRoute([0], [(start.longitude, start.latitude), (end.longitude, end.latitude)])
        remaining = self.deadline - monotonic()
        if remaining <= 0 or not _ROUTER_LOCK.acquire(timeout=max(0, remaining)):
            raise PlanningError("provider_timeout", "Routino calculation budget expired.", 504)
        try:
            remaining = self.deadline - monotonic()
            if remaining <= 0:
                raise PlanningError("provider_timeout", "Routino calculation budget expired.", 504)
            command = [self.binary, f"--dir={self.database}", f"--profiles={self.profiles}", f"--translations={self.translations}", "--profile=distance-car", "--shortest", "--quiet", "--output-text-all", "--output-stdout", f"--lat1={start.latitude}", f"--lon1={start.longitude}", f"--lat2={end.latitude}", f"--lon2={end.longitude}"]
            try:
                result = subprocess.run(command, capture_output=True, text=True, timeout=min(15, remaining), check=False)
            except subprocess.TimeoutExpired:
                raise PlanningError("provider_timeout", "Routino route calculation timed out.", 504) from None
            except OSError:
                raise PlanningError("provider_unavailable", "Routino could not be started.", 503) from None
        finally:
            _ROUTER_LOCK.release()
        if result.returncode:
            # These known messages mean a legal route cannot be found. Other
            # failures (e.g. missing graph files) are configuration/service errors.
            unreachable = ("Cannot find initial section of route", "Cannot find final section of route", "Cannot find super-route")
            if any(message in result.stderr for message in unreachable):
                return None
            if "Cannot find node close to specified point" in result.stderr:
                waypoint = re.search(r"Cannot find node close to specified point ([12])\b", result.stderr)
                ids = [start.id if waypoint[1] == "1" else end.id] if waypoint else []
                raise PlanningError("location_not_routable", "A location has no nearby routable road. Confirm its map position.", location_ids=ids)
            raise PlanningError("provider_failed", "Routino failed to calculate this route.", 502)
        return self.parse_output(result.stdout)

    @staticmethod
    def parse_output(text: str) -> RoadRoute:
        try:
            rows = [line.split("\t") for line in text.splitlines() if line.strip() and not line.startswith("#")]
            if len(rows) < 2:
                raise ValueError()
            coordinates = [(float(row[1]), float(row[0])) for row in rows]
            distance = float(rows[-1][6]) * 1000
            if not math.isfinite(distance) or distance < 0:
                raise ValueError()
            if any(not math.isfinite(lon) or not math.isfinite(lat) or not (-180 <= lon <= 180 and -90 <= lat <= 90) for lon, lat in coordinates):
                raise ValueError()
            # CLI cumulative distances have 0.01 km precision (10 meters).
            return RoadRoute([round(distance)], coordinates)
        except (IndexError, ValueError):
            raise PlanningError("invalid_provider_response", "Routino returned invalid route output.", 502) from None

    def distance_matrix(self, points: list[Point], policy: RoadPolicy) -> Matrix:
        self._policy(policy)
        matrix: Matrix = [[0 for _ in points] for _ in points]
        for i, start in enumerate(points):
            for j, end in enumerate(points):
                if i != j:
                    leg = self._leg(start, end)
                    matrix[i][j] = leg.leg_distances[0] if leg else None
        # Do not retain every pair's geometry: it could consume more memory than
        # the routing process. Recalculate geometry only for selected legs.
        return matrix

    def route(self, ordered_points: list[Point], policy: RoadPolicy) -> RoadRoute:
        self._policy(policy)
        distances, coordinates = [], []
        for start, end in zip(ordered_points, ordered_points[1:]):
            leg = self._leg(start, end)
            if leg is None:
                raise PlanningError("unreachable_leg", "No car route connects these consecutive locations.", location_ids=[start.id, end.id])
            distances.extend(leg.leg_distances)
            coordinates.extend(leg.coordinates[1:] if coordinates and coordinates[-1] == leg.coordinates[0] else leg.coordinates)
        return RoadRoute(distances, coordinates)
