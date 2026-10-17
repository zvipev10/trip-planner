from fastapi.testclient import TestClient
from app.main import app


def test_web_is_served_without_routing_configuration():
    with TestClient(app) as client:
        page = client.get('/web/')
        assert page.status_code == 200
        assert 'Trip Planner' in page.text
        assert './app.mjs' in page.text
        for asset in ('app.mjs', 'core.mjs', 'style.css'):
            assert client.get('/web/' + asset).status_code == 200


def test_home_redirect_is_relative_for_reverse_proxy_prefix():
    with TestClient(app) as client:
        response = client.get('/', follow_redirects=False)
        assert response.status_code == 307
        assert response.headers['location'] == 'web/'
