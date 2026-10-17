from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Point(Model):
    id: str = Field(min_length=1, max_length=100)
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)


class RoadPolicy(Model):
    # Provisional defaults; finalize after provider validation.
    avoid_tolls: bool = Field(default=False, alias="avoidTolls")
    avoid_ferries: bool = Field(default=True, alias="avoidFerries")
    avoid_unpaved: bool = Field(default=True, alias="avoidUnpaved")


class RouteRequest(Model):
    revision: int = Field(ge=0)
    start: Point
    end: Point
    stops: list[Point] = Field(default_factory=list, max_length=20)
    road_policy: RoadPolicy = Field(default_factory=RoadPolicy, alias="roadPolicy")

    @model_validator(mode="after")
    def unique_ids(self):
        points = [self.start, *self.stops, self.end]
        if len({p.id for p in points}) != len(points):
            raise ValueError("Point IDs must be unique; for a round trip use distinct endpoint IDs with equal coordinates")
        return self

    @property
    def points(self) -> list[Point]:
        return [self.start, *self.stops, self.end]


class Geometry(Model):
    type: Literal["LineString"] = "LineString"
    coordinates: list[tuple[
        Annotated[float, Field(ge=-180, le=180, allow_inf_nan=False)],
        Annotated[float, Field(ge=-90, le=90, allow_inf_nan=False)],
    ]] = Field(min_length=2)


class RouteResponse(Model):
    revision: int
    ordered_stop_ids: list[str] = Field(alias="orderedStopIds")
    distance_meters: int = Field(alias="distanceMeters")
    leg_distances_meters: list[int] = Field(alias="legDistancesMeters")
    geometry: Geometry
    status: str
    provider: str
