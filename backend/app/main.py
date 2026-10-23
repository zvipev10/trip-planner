from pathlib import Path
import json
import logging
from time import monotonic
from uuid import uuid4
from .diagnostics import event, request_id

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from .config import configured_provider
from .models import Geometry, RouteRequest, RouteResponse
from .places import PlaceLinkRequest, resolve_place
from .provider import PlanningError, RoutingProvider, UnconfiguredProvider
from .solver import optimize, validate_matrix

app = FastAPI(title="Israel Trip Planner", version="0.1.0")
logger = logging.getLogger("uvicorn.error")
app.mount("/web", StaticFiles(directory=Path(__file__).with_name("web"), html=True), name="web")


@app.get("/", include_in_schema=False)
def web_home():
    return RedirectResponse("web/")


def get_provider() -> RoutingProvider:
    return configured_provider()


@app.exception_handler(PlanningError)
async def planning_error(_request: Request, exc: PlanningError):
    logger.warning("routing_failure status=%s code=%s", exc.status, exc.code)
    return JSONResponse(status_code=exc.status, content={"error": {"code": exc.code, "message": exc.message, "locationIds": exc.location_ids}})


@app.exception_handler(RequestValidationError)
async def invalid_request(_request: Request, _exc: RequestValidationError):
    # Never log inputs, error messages/context, point IDs, or unknown field names:
    # validation errors can contain entire request bodies and private locations.
    fields = {"body", "revision", "start", "end", "stops", "id", "latitude", "longitude", "roadPolicy", "avoidTolls", "avoidFerries", "avoidUnpaved"}
    errors = [{"type": error["type"], "field": [part if isinstance(part, int) or part in fields else "unknown" for part in error["loc"]]} for error in _exc.errors()[:20]]
    body = _exc.body if isinstance(_exc.body, dict) else {}
    stops = body.get("stops")
    points = [body.get("start"), *(stops if isinstance(stops, list) else []), body.get("end")]
    ids = [point.get("id") for point in points if isinstance(point, dict) and isinstance(point.get("id"), str)]
    duplicate_ids = len(ids) != len(set(ids))
    endpoint = _request.url.path.rsplit("/", 1)[-1]
    endpoint = endpoint if endpoint in {"optimize", "calculate", "resolve"} else "other"
    logger.warning("request_validation_failed %s", json.dumps({"endpoint": endpoint, "errors": errors, "stopCount": len(stops) if isinstance(stops, list) else None, "duplicatePointIds": duplicate_ids}))
    return JSONResponse(status_code=422, content={"error": {"code": "invalid_request", "message": "Check endpoint coordinates, unique location IDs, and the 20-stop limit.", "locationIds": []}})


@app.get("/health")
def health(provider: RoutingProvider = Depends(get_provider)):
    return {"status": "ok", "routingProvider": provider.name, "routingConfigured": not isinstance(provider, UnconfiguredProvider)}


def calculate(request: RouteRequest, provider: RoutingProvider, reorder: bool):
    token = request_id.set(uuid4().hex[:16])
    started = monotonic()
    event("started", mode="optimize" if reorder else "calculate", pointCount=len(request.points), sameEndpoints=(request.start.latitude == request.end.latitude and request.start.longitude == request.end.longitude))
    try:
        submitted_policy = request.road_policy
        if callable(getattr(provider, "effective_policy", None)):
            request = request.model_copy(update={"road_policy": provider.effective_policy(submitted_policy)})
        event("request", provider=provider.name, routingProfile=getattr(provider, "diagnostic_profile", None), payload=request.model_dump(mode="json", by_alias=True), submittedRoadPolicy=submitted_policy.model_dump(mode="json", by_alias=True))
        result = _calculate(request, provider, reorder)
        event("completed", elapsedMs=round((monotonic() - started) * 1000))
        return result
    except PlanningError as exc:
        event("failed", code=exc.code, status=exc.status, message=exc.message, locationIds=exc.location_ids, elapsedMs=round((monotonic() - started) * 1000))
        raise
    except Exception:
        event("failed", code="unexpected_error", elapsedMs=round((monotonic() - started) * 1000))
        raise
    finally:
        request_id.reset(token)


def _calculate(request: RouteRequest, provider: RoutingProvider, reorder: bool):
    points = request.points
    if reorder:
        started = monotonic()
        event("matrix_started")
        matrix = provider.distance_matrix(points, request.road_policy)
        validate_matrix(matrix, len(points))
        event("matrix_ready", distances=matrix, elapsedMs=round((monotonic() - started) * 1000), unreachablePairs=[[i, j] for i, row in enumerate(matrix) for j, value in enumerate(row) if i != j and value is None], noOutgoing=[i for i in range(len(points) - 1) if all(matrix[i][j] is None for j in range(1, len(points)) if i != j)], noIncoming=[j for j in range(1, len(points)) if all(matrix[i][j] is None for i in range(len(points) - 1) if i != j)])
        order = optimize(matrix)
    else:
        order = list(range(len(points)))
    ordered = [points[index] for index in order]
    event("route_started", order=order)
    started = monotonic()
    road = provider.route(ordered, request.road_policy)
    event("route_ready", elapsedMs=round((monotonic() - started) * 1000), legCount=len(road.leg_distances))
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


@app.post("/v1/places/resolve")
async def resolve_shared_place(request: PlaceLinkRequest):
    return await resolve_place(request.text)
