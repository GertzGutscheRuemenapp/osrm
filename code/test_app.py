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
    """test the overview of the router"""
    response = client.get("/")
    assert response.status_code == 200
    assert b"OSRM Wrapper" in response.data


def build(client):
    """build the router"""
    fp = os.path.join(os.path.dirname(__file__), 'testdata', 'test.osm.pbf')
    files = {'file': open(fp, 'rb'),
             'algoritm': 'ch', }

    response = client.post("/build/foot", data=files)
    assert response.status_code == 200


def test_build(client):
    """Test the building of a container"""
    fp = os.path.join(os.path.dirname(__file__), 'testdata', 'test.osm.pbf')
    files = {'file': open(fp, 'rb')}

    # mode velocopter does not exist
    response = client.post("/build/velocopter", data=files)
    assert response.status_code == 400

    # no pbf-file provided
    response = client.post("/build/foot")
    assert response.status_code == 400

    # this should work
    files = {'file': open(fp, 'rb'),
             'algorithm': 'ch'}
    response = client.post("/build/foot", data=files)
    assert response.status_code == 200

    #params['algorithm'] = 'ch'
    files = {'file': open(fp, 'rb'),
             'algorithm': 'mld'}
    # this should work with other algorithm
    response = client.post("/build/foot", data=files)
    assert response.status_code == 200


def test_run(client):
    """Test running the router"""
    # build network
    build(client)

    # start the router
    response = client.post("/run/foot", data={'algoritm': 'ch'}, )
    assert response.status_code == 200
    sleep(0.2)

    # url and params to call the router
    base_url = 'http://localhost:5003'
    lat, lon = 9.0, 50.4
    coords = f'{lat},{lon}'
    url = f'{base_url}/nearest/v1/driving/{coords}'
    data = {'number': 3, }

    # stop the router
    response = client.post("/stop/foot")
    assert response.status_code == 200
    sleep(0.2)

    # now it should not be available
    with pytest.raises(requests.exceptions.ConnectionError) as e_info:
        res = requests.get(url, params=data)

    # start it again
    response = client.post("/run/foot")
    assert response.status_code == 200
    sleep(0.2)

    # now it should be available
    res = requests.get(url, params=data)
    assert response.status_code == 200

    # and return 3 matched nodes
    nearest = res.json()
    assert nearest['code'] == 'Ok'
    wpts = nearest['waypoints']
    assert len(wpts) == 3


def test_remove(client):
    """remove the router"""
    # build the router
    build(client)

    # now the routing files should be in the data subfolder
    d = os.listdir(os.path.join(os.path.dirname(__file__), 'data'))
    assert 'foot.osrm.edges' in d

    # run it
    response = client.post("/run/foot")
    assert response.status_code == 200
    sleep(0.2)

    # now stop and remove it
    response = client.post("/remove/foot")
    assert response.status_code == 200

    # now only the pbf-file should be left
    d = os.listdir(os.path.join(os.path.dirname(__file__), 'data'))
    assert d == ['foot.pbf']
