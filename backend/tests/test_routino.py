from pathlib import Path
import subprocess

import pytest

from app.models import Point, RoadPolicy
from app.provider import PlanningError
from app.routino import RoutinoProvider

BASE = Path(__file__).resolve().parents[2] / 'routino'
VENDOR = BASE / 'vendor/routino-3.4.4'


def test_parser_coordinate_order_and_distance_precision():
    output = '# header\n32.08\t34.78\t0\tWaypt#1\t0\t0\t0.00\n32.06\t34.77\t1\tWaypt#2\t0\t0\t3.29\n'
    result = RoutinoProvider.parse_output(output)
    assert result.leg_distances == [3290]
    assert result.coordinates == [(34.78, 32.08), (34.77, 32.06)]


@pytest.mark.parametrize('output', ['', '# only header', 'bad\trow', '32\t181\t0\tx\t0\t0\t1\n32\t35\t1\tx\t0\t0\t2'])
def test_malformed_output(output):
    with pytest.raises(PlanningError):
        RoutinoProvider.parse_output(output)


def test_does_not_ignore_unsupported_preferences():
    with pytest.raises(PlanningError) as exc:
        RoutinoProvider._policy(RoadPolicy(avoidTolls=True))
    assert exc.value.code == 'unsupported_road_policy'


@pytest.mark.skipif(not (BASE/'data/fixture/nodes.mem').exists(), reason='Build the optional Routino fixture first')
def test_real_binary_distance_objective():
    provider = RoutinoProvider(str(VENDOR/'src/router-slim'), str(BASE/'data/fixture'), str(BASE/'profiles/distance-car.xml'), str(VENDOR/'xml/routino-translations.xml'))
    start = Point(id='a', latitude=32.080, longitude=34.780)
    end = Point(id='b', latitude=32.080, longitude=34.790)
    shortest = provider.route([start, end], RoadPolicy())
    assert shortest.leg_distances == [940]  # CLI cumulative precision is 10 m.
    assert all(abs(lat - 32.080) < 0.00001 for _, lat in shortest.coordinates)
    command = [provider.binary, f'--dir={provider.database}', f'--profiles={provider.profiles}', f'--translations={provider.translations}', '--profile=distance-car', '--quickest', '--lat1=32.080', '--lon1=34.780', '--lat2=32.080', '--lon2=34.790', '--quiet', '--output-text-all', '--output-stdout']
    quickest = provider.parse_output(subprocess.run(command, check=True, text=True, capture_output=True).stdout)
    assert quickest.leg_distances[0] == 3170
    assert shortest.leg_distances[0] < quickest.leg_distances[0]

@pytest.mark.parametrize('waypoint,expected', [('1', ['first']), ('2', ['second']), ('unknown', [])])
def test_unroutable_error_identifies_only_failed_waypoint(monkeypatch, waypoint, expected):
    from time import monotonic
    provider = object.__new__(RoutinoProvider)
    provider.binary = provider.database = provider.profiles = provider.translations = 'fixture'
    provider.deadline = monotonic() + 60
    monkeypatch.setattr(subprocess, 'run', lambda *args, **kwargs: subprocess.CompletedProcess([], 1, '', f'Error: Cannot find node close to specified point {waypoint}.'))
    with pytest.raises(PlanningError) as exc:
        provider._leg(Point(id='first', latitude=32, longitude=35), Point(id='second', latitude=33, longitude=35))
    assert exc.value.code == 'location_not_routable'
    assert exc.value.location_ids == expected
