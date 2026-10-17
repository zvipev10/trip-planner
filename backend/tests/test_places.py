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
