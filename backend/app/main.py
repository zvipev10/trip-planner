from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from .config import configured_provider
from .models import Geometry, RouteRequest, RouteResponse
from .provider import PlanningError, RoutingProvider, UnconfiguredProvider
from .solver import optimize, validate_matrix

app = FastAPI(title="Israel Trip Planner", version="0.1.0")
app.mount("/web", StaticFiles(directory=Path(__file__).with_name("web"), html=True), name="web")


@app.get("/", include_in_schema=False)
def web_home():
    return RedirectResponse("web/")


def get_provider() -> RoutingProvider:
    return configured_provider()


@app.exception_handler(PlanningError)
async def planning_error(_request: Request, exc: PlanningError):
    return JSONResponse(status_code=exc.status, content={"error": {"code": exc.code, "message": exc.message, "locationIds": exc.location_ids}})


@app.exception_handler(RequestValidationError)
async def invalid_request(_request: Request, _exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"error": {"code": "invalid_request", "message": "Check endpoint coordinates, unique location IDs, and the 20-stop limit.", "locationIds": []}})


@app.get("/health")
def health(provider: RoutingProvider = Depends(get_provider)):
    return {"status": "ok", "routingProvider": provider.name, "routingConfigured": not isinstance(provider, UnconfiguredProvider)}


def calculate(request: RouteRequest, provider: RoutingProvider, reorder: bool):
    points = request.points
    if reorder:
        matrix = provider.distance_matrix(points, request.road_policy)
        validate_matrix(matrix, len(points))
        order = optimize(matrix)
    else:
        order = list(range(len(points)))
    ordered = [points[index] for index in order]
    road = provider.route(ordered, request.road_policy)
    if len(road.leg_distances) != len(ordered) - 1 or any(type(d) is not int or d < 0 for d in road.leg_distances):
        raise PlanningError("invalid_provider_response", "Routing provider returned invalid legs.", 502)
    if len(road.coordinates) < 2:
        raise PlanningError("invalid_provider_response", "Routing provider returned missing geometry.", 502)
    if reorder:
        expected = [matrix[a][b] for a, b in zip(order, order[1:])]
        # Permit integer-meter rounding, never silently display a different profile.
        if any(a is None or abs(a - b) > max(2, a * 0.001) for a, b in zip(expected, road.leg_distances)):
            raise PlanningError("routing_profile_mismatch", "Matrix and route distances disagree; provider validation is required.", 502)
    try:
        geometry = Geometry(coordinates=road.coordinates)
    except ValidationError as exc:
        raise PlanningError("invalid_provider_response", "Routing provider returned invalid geometry.", 502) from exc
    return RouteResponse(revision=request.revision, orderedStopIds=[p.id for p in ordered[1:-1]], distanceMeters=sum(road.leg_distances), legDistancesMeters=road.leg_distances, geometry=geometry, status="optimized" if reorder else "manual", provider=provider.name)


@app.post("/v1/routes/optimize", response_model=RouteResponse)
def optimize_route(request: RouteRequest, provider: RoutingProvider = Depends(get_provider)):
    return calculate(request, provider, True)


@app.post("/v1/routes/calculate", response_model=RouteResponse)
def calculate_route(request: RouteRequest, provider: RoutingProvider = Depends(get_provider)):
    return calculate(request, provider, False)
