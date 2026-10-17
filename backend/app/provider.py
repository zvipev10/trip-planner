from dataclasses import dataclass
from typing import Protocol

from .models import Point, RoadPolicy

Matrix = list[list[int | None]]


class PlanningError(Exception):
    def __init__(self, code: str, message: str, status: int = 422, location_ids: list[str] | None = None):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status
        self.location_ids = location_ids or []


@dataclass
class RoadRoute:
    leg_distances: list[int]
    # GeoJSON order: longitude, latitude.
    coordinates: list[tuple[float, float]]


class RoutingProvider(Protocol):
    name: str

    def distance_matrix(self, points: list[Point], policy: RoadPolicy) -> Matrix:
        """Directed integer-meter distances; None means no legal route.

        Use the same shortest-distance road profile as route(). Never substitute
        straight-line distances or durations. Do not log submitted coordinates.
        """
        ...

    def route(self, ordered_points: list[Point], policy: RoadPolicy) -> RoadRoute: ...


class UnconfiguredProvider:
    name = "unconfigured"

    def distance_matrix(self, points, policy):
        raise PlanningError("provider_not_configured", "Connect a validated road-routing provider before calculating real trips.", 503)

    def route(self, ordered_points, policy):
        raise PlanningError("provider_not_configured", "Connect a validated road-routing provider before calculating real trips.", 503)
