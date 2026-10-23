import json
import httpx
import pytest
from app.config import configured_provider
from app.models import Point,RoadPolicy
from app.provider import PlanningError
from app.valhalla_provider import ValhallaProvider

POINTS=[Point(id='start',latitude=32.08,longitude=34.78),Point(id='end',latitude=32.09,longitude=34.79)]


def reply(distance=1.234,coords=None):
    return {'trip':{'status':0,'units':'kilometers','legs':[{'summary':{'length':distance},'shape':{'type':'LineString','coordinates':coords or [[34.78,32.08],[34.79,32.09]]}}]}}


def test_directed_pair_distances_and_matching_policy():
    calls=[]
    def handler(request):
        payload=json.loads(request.content);calls.append(payload)
        assert request.url.path=='/route'
        assert payload['costing_options']['auto']=={'shortest':True,'disable_hierarchy_pruning':True,'exclude_unpaved':True,'exclude_ferries':True,'exclude_tolls':False}
        forward=payload['locations'][0]['lat']==32.08
        return httpx.Response(200,json=reply(1.234 if forward else 2.345))
    engine=ValhallaProvider(transport=httpx.MockTransport(handler))
    policy=RoadPolicy()
    assert engine.distance_matrix(POINTS,policy)==[[0,1234],[2345,0]]
    assert engine.route(POINTS,policy).leg_distances==[1234]
    assert len(calls)==3
    assert all(value is None or isinstance(value,int) for value in engine.distances.values())


def test_round_trip_and_explicit_policy_relaxation():
    def handler(request):
        options=json.loads(request.content)['costing_options']['auto']
        assert options['exclude_unpaved'] is False and options['exclude_tolls'] is True
        return httpx.Response(200,json=reply())
    engine=ValhallaProvider(transport=httpx.MockTransport(handler))
    assert engine.route(POINTS,RoadPolicy(avoidUnpaved=False,avoidTolls=True)).leg_distances==[1234]
    end=POINTS[0].model_copy(update={'id':'round-end'})
    assert engine.route([POINTS[0],end],RoadPolicy()).leg_distances==[0]


def test_disconnected_pair_and_location_errors():
    engine=ValhallaProvider(transport=httpx.MockTransport(lambda _:httpx.Response(400,json={'error_code':442})))
    assert engine.distance_matrix(POINTS,RoadPolicy())==[[0,None],[None,0]]
    with pytest.raises(PlanningError) as error:engine.route(POINTS,RoadPolicy())
    assert error.value.code=='unreachable_leg' and error.value.location_ids==['start','end']
    engine=ValhallaProvider(transport=httpx.MockTransport(lambda _:httpx.Response(400,json={'error_code':171})))
    with pytest.raises(PlanningError) as error:engine.route(POINTS,RoadPolicy())
    assert error.value.code=='location_not_routable'


@pytest.mark.parametrize('value',[-1,True,float('nan')])
def test_invalid_distance(value):
    # Non-JSON NaN is handled as malformed JSON upstream, so use raw body.
    response=json.dumps(reply(value))
    engine=ValhallaProvider(transport=httpx.MockTransport(lambda _:httpx.Response(200,text=response)))
    with pytest.raises(PlanningError) as error:engine.route(POINTS,RoadPolicy())
    assert error.value.code=='invalid_provider_response'


def test_bad_geometry_and_timeout():
    engine=ValhallaProvider(transport=httpx.MockTransport(lambda _:httpx.Response(200,json=reply(coords=[[999,32],[35,32]]))))
    with pytest.raises(PlanningError) as error:engine.route(POINTS,RoadPolicy())
    assert error.value.code=='invalid_provider_response'
    engine=ValhallaProvider(transport=httpx.MockTransport(lambda _:httpx.Response(504,json={'error':'private upstream text'})))
    with pytest.raises(PlanningError) as error:engine.route(POINTS,RoadPolicy())
    assert error.value.code=='provider_timeout' and 'private' not in str(error.value)
    engine.deadline=0
    with pytest.raises(PlanningError) as error:engine.route(POINTS,RoadPolicy())
    assert error.value.code=='provider_timeout'


def test_configuration_validation_gate_and_local_only(monkeypatch):
    monkeypatch.setenv('ROUTING_PROVIDER','valhalla');monkeypatch.delenv('VALHALLA_DISTANCE_VALIDATED',raising=False)
    with pytest.raises(PlanningError) as error:configured_provider()
    assert error.value.code=='distance_profile_unvalidated'
    monkeypatch.setenv('VALHALLA_DISTANCE_VALIDATED','true')
    assert configured_provider().name=='valhalla'
    monkeypatch.setenv('VALHALLA_BASE_URL','http://remote.example')
    with pytest.raises(PlanningError) as error:configured_provider()
    assert error.value.code=='provider_configuration_error'


def test_native_polyline6_and_malformed_geometry():
    from app.valhalla_provider import decode_polyline6
    assert decode_polyline6('??AC')==[(0.0,0.0),(0.000002,0.000001)]
    data=reply();data['trip']['legs'][0]['shape']='??AC'
    engine=ValhallaProvider(transport=httpx.MockTransport(lambda _:httpx.Response(200,json=data)))
    assert engine.route(POINTS,RoadPolicy()).coordinates==[(0.0,0.0),(0.000002,0.000001)]
    for bad in ['_','!','?']:
        with pytest.raises(ValueError):decode_polyline6(bad)
