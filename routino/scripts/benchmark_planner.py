"""Measure actual backend calculation plus slim routing on local Tel Aviv stops."""
import json
from pathlib import Path
import resource
from time import perf_counter

from app.main import calculate
from app.models import Point, RouteRequest
from app.routino import RoutinoProvider

base = Path(__file__).resolve().parents[1]
vendor = base/'vendor/routino-3.4.4'
results = []
for count in (5, 20):
    provider = RoutinoProvider(str(vendor/'src/router-slim'), str(base/'data/israel'), str(base/'profiles/distance-car.xml'), str(vendor/'xml/routino-translations.xml'))
    points = [Point(id=f'p{i}', latitude=32.060 + (i//5)*0.004, longitude=34.770+(i%5)*0.004) for i in range(count+2)]
    request = RouteRequest(revision=1, start=points[0], end=points[-1], stops=points[1:-1])
    started = perf_counter()
    response = calculate(request, provider, True)
    record = dict(intermediateStops=count, directedPairRequests=(count+2)*(count+1), selectedLegRequests=count+1, wallSeconds=round(perf_counter()-started, 3), backendPeakRssMiB=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024, 2), childPeakRssMiB=round(resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss/1024, 2), distanceMeters=response.distance_meters, allStopsOnce=sorted(response.ordered_stop_ids)==sorted(p.id for p in points[1:-1]))
    results.append(record)
    print(json.dumps(record), flush=True)
(base/'runs/planner-summary.json').write_text(json.dumps(results, indent=2)+'\n')
