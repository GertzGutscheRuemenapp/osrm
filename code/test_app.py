import os
import pytest
import requests
from time import sleep
from app import app as flask_app


@pytest.fixture()
def app():
    flask_app.config.update({
        "TESTING": True,
    })
    #flask_app.run(host="0.0.0.0", port=8001, use_reloader=True)

    # other setup can go here

    yield flask_app

    # clean up / reset resources here


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def runner(app):
    return app.test_cli_runner()


def test_get(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"OSRM Wrapper" in response.data


def build(client):
    fp = os.path.join(os.path.dirname(__file__), 'testdata', 'network.pbf')
    files = {'file': open(fp, 'rb')}

    response = client.post("/build/velocopter", data={'files': files})
    assert response.status_code == 400

    response = client.post("/build/foot", data=files)
    assert response.status_code == 200


def test_build(client):
    fp = os.path.join(os.path.dirname(__file__), 'testdata', 'network.pbf')
    files = {'file': open(fp, 'rb')}

    response = client.post("/build/velocopter", data={'files': files})
    assert response.status_code == 400

    response = client.post("/build/foot", data=files)
    assert response.status_code == 200


def test_run(client):
    build(client)
    response = client.post("/run/foot")
    assert response.status_code == 200
    sleep(0.2)

    base_url = 'http://localhost:5003'
    lat, lon = 9.0, 50.4
    coords = f'{lat},{lon}'
    url = f'{base_url}/nearest/v1/driving/{coords}'
    data = {'number': 3, }
    res = requests.get(url, params=data)
    assert response.status_code == 200
    nearest = res.json()
    assert nearest['code'] == 'Ok'
    wpts = nearest['waypoints']
    assert len(wpts) == 3


def test_remove(client):
    build(client)
    response = client.post("/run/foot")
    assert response.status_code == 200
    sleep(0.2)

    response = client.post("/remove/foot")
    assert response.status_code == 200
    d = os.listdir(os.path.join(os.path.dirname(__file__), 'data'))
    assert d == ['foot.pbf']
