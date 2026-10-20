import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.places import allowed, parse_place, resolve_place
from app.provider import PlanningError


@pytest.mark.parametrize('text', [
    'https://www.google.com/maps/place/Cafe+Five/data=!4m2!3d32.08!4d34.78',
    'https://waze.com/ul?ll=32.08%2C34.78&navigate=yes',
    'https://maps.google.com/?q=32.08,34.78',
])
def test_destination_coordinates(text):
    result = parse_place(text)
    assert result['latitude'] == 32.08
    assert result['longitude'] == 34.78


def test_name_and_camera_rejection():
    assert parse_place('https://google.com/maps/place/Cafe+Five/@32,34,16z')['name'] == 'Cafe Five'
    assert 'latitude' not in parse_place('https://google.com/maps/@32,34,16z')


@pytest.mark.parametrize('url', ['https://127.0.0.1/', 'http://google.com/', 'https://google.com.evil.test/', 'https://user@google.com/', 'https://google.com:8080/', 'https://google.com:bad/'])
def test_fetch_allowlist(url):
    assert not allowed(url)


def test_short_link_redirect_resolves():
    def handler(request):
        assert request.url.host == 'maps.app.goo.gl'
        return httpx.Response(302, headers={'location': 'https://www.google.com/maps/place/Cafe+Five/data=!3d32.08!4d34.78'})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await resolve_place('https://maps.app.goo.gl/example', client)
    assert asyncio.run(run()) == {'name': 'Cafe Five', 'latitude': 32.08, 'longitude': 34.78}


def test_redirect_to_private_host_is_never_requested():
    seen = []
    def handler(request):
        seen.append(request.url.host)
        return httpx.Response(302, headers={'location': 'https://127.0.0.1/private'})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await resolve_place('https://maps.app.goo.gl/example', client)
    with pytest.raises(PlanningError, match='unsupported'):
        asyncio.run(run())
    assert seen == ['maps.app.goo.gl']


def test_unrelated_page_coordinates_are_not_a_destination():
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, text='unrelated marker !3d32!4d34'))) as client:
            await resolve_place('https://maps.app.goo.gl/example', client)
    with pytest.raises(PlanningError, match='destination position'):
        asyncio.run(run())


def test_place_endpoint():
    with TestClient(app) as client:
        response = client.post('/v1/places/resolve', json={'text': 'https://waze.com/ul?ll=32.08,34.78'})
    assert response.status_code == 200
    assert response.json()['latitude'] == 32.08


def test_waze_short_link_to_geohash():
    async def run():
        transport = httpx.MockTransport(lambda _: httpx.Response(302, headers={'location': 'https://waze.com/ul/hsv8wrqkp9'}))
        async with httpx.AsyncClient(transport=transport) as client:
            return await resolve_place('https://ul.waze.com/ul/example', client)
    place = asyncio.run(run())
    assert 29 < place['latitude'] < 34
    assert 34 < place['longitude'] < 36


@pytest.mark.parametrize("reverse", [False, True])
def test_canonical_destination_metadata(reverse):
    async def run():
        page = '<link rel="canonical" href="https://google.com/maps/place/Cafe+Five/data=!3d32.08!4d34.78"><meta property="og:title" content="Cafe Five - Google Maps">'
        if reverse:
            page = page.replace('rel="canonical" href=', 'href=').replace('!4d34.78">', '!4d34.78" rel="canonical">')
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, text=page))) as client:
            return await resolve_place('https://maps.app.goo.gl/example', client)
    assert asyncio.run(run()) == {'name': 'Cafe Five', 'latitude': 32.08, 'longitude': 34.78}


# Exact feature ID/address format returned by the user's Google short link.
USER_FTID = '0x151d49f6e6ba521d:0xe00153be1828da13'
USER_ADDRESS = "קרית אריה, Ef'al St 7, Petah Tikva"


def embed_fixture(ftid=USER_FTID, latitude=32.0935124):
    import json
    # Conflicting camera coordinates must not be selected. Destination is keyed by ID.
    payload = [None, [[[3380.1, 34.0, 31.0], [0, 0, 0]], None, None,
                      [[ftid, USER_ADDRESS, [latitude, 34.8482224], '16141274615386790419'], 'קרית אריה']]]
    return '<script>initEmbed(' + json.dumps(payload, ensure_ascii=False) + ');</script>'


def test_exact_user_short_link_resolves_feature_id():
    calls = []
    def handler(request):
        calls.append(request.url)
        if request.url.host == 'maps.app.goo.gl':
            return httpx.Response(302, headers={'location': str(httpx.URL('https://maps.google.com', params={'q': USER_ADDRESS, 'ftid': USER_FTID, 'g_st': 'ic'}))})
        assert request.url.host == 'www.google.com'
        if request.url.path == '/maps':
            assert request.url.params['output'] == 'embed'
            assert request.url.params['ftid'] == USER_FTID
            assert 'g_st' not in request.url.params
            return httpx.Response(301, headers={'location': 'https://www.google.com/maps/embed?pb=opaque-feature-data'})
        assert request.url.path == '/maps/embed'
        return httpx.Response(200, text=embed_fixture())
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await resolve_place('https://maps.app.goo.gl/SZuQY5qwP4PJ8woF8?g_st=ic', client)
    assert asyncio.run(run()) == {'name': 'קרית אריה', 'latitude': 32.0935124, 'longitude': 34.8482224}
    assert len(calls) == 3


@pytest.mark.parametrize('page', [
    embed_fixture(ftid='0x111:0x222'),
    embed_fixture(latitude=100),
    '<script>initEmbed([[[3380.1,34.8482224,32.0935124]]]);</script>',
    '<script>initEmbed(notValidJSON);</script>',
])
def test_embedded_destination_requires_matching_id_and_valid_position(page):
    from app.places import embedded_google_place
    assert embedded_google_place(page, USER_FTID) is None


def test_real_embed_response_shape():
    from app.places import embedded_google_place
    # Reproduces the destination container from the live Google embed response.
    page = 'initEmbed([null,null,[[[3380.10250890583,34.8482224,32.0935124],[0,0,0],null,13.1],null,null,[["' + USER_FTID + '","קרית אריה, Ef\'al St 7, Petah Tikva, Israel",[32.0935124,34.8482224],"16141274615386790419"],"קרית אריה",["Ef\'al St 7","Petah Tikva","Israel"]]]]);'
    assert embedded_google_place(page, USER_FTID)['name'] == 'קרית אריה'


ANDROID_SHARE_FTID = '0x151c14823463a7d9:0xa0ccbe2b317840e2'
ANDROID_SHARE_PATH = 'https://www.google.com/maps/place/%D7%A2%D7%99%D7%9F+%D7%A9%D7%95%D7%A7%D7%95/data=!4m2!3m1!1s' + ANDROID_SHARE_FTID + '!18m1!1e1?entry=gps'


@pytest.mark.parametrize('url', [ANDROID_SHARE_PATH, ANDROID_SHARE_PATH.replace('!1s', '%211s').replace(':0x', '%3A0x')])
def test_google_feature_id_in_android_share_path(url):
    from app.places import google_embed_url
    result, ftid = google_embed_url(url)
    query = httpx.URL(result).params
    assert ftid == ANDROID_SHARE_FTID
    assert query['ftid'] == ftid
    assert query['q'] == 'עין שוקו'
    assert query['output'] == 'embed'


def test_android_short_link_path_id_round_trip():
    import json
    calls = []
    def handler(request):
        calls.append(request.url)
        if request.url.host == 'maps.app.goo.gl':
            return httpx.Response(302, headers={'location': ANDROID_SHARE_PATH})
        assert request.url.host == 'www.google.com'
        assert request.url.params['ftid'] == ANDROID_SHARE_FTID
        assert request.url.params['output'] == 'embed'
        payload = [[ANDROID_SHARE_FTID, 'עין שוקו', [32.7389393, 35.6507361]], 'עין שוקו']
        return httpx.Response(200, text='initEmbed(' + json.dumps(payload) + ');')
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await resolve_place('https://maps.app.goo.gl/ckFFYsB7ADuppy5d9?g_st=ac', client)
    assert asyncio.run(run()) == {'name': 'עין שוקו', 'latitude': 32.7389393, 'longitude': 35.6507361}
    assert len(calls) == 2
