import os
import glob
from time import sleep
import pytest
import requests
from retry import retry
from app import app as flask_app


@pytest.fixture()
def app():
    flask_app.config.update({
        "TESTING": True,
    })

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
             'algorithm': 'mld', }

    response = client.post("/build/foot", data=files)
    assert response.status_code == 200
    
    files = {'file': open(fp, 'rb'),
             'algorithm': 'ch', }

    response = client.post("/build/car", data=files)
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
    response = client.post("/run/foot", data={'algorithm': 'mld'}, )
    assert response.status_code == 200
    sleep(0.5)

    # url and params to call the router
    foot_port = os.environ.get('MODE_FOOT_PORT', 5003)
    base_url = f'http://localhost:{foot_port}'
    lat, lon = 9.0, 50.4
    coords = f'{lat},{lon}'
    url = f'{base_url}/nearest/v1/driving/{coords}'
    data = {'number': 3, }

    # stop the router
    response = client.post("/stop/foot")
    assert response.status_code == 200
    sleep(0.5)

    # now it should not be available
    with pytest.raises(requests.exceptions.ConnectionError) as e_info:
        res = call_url(url, data)

    # start it again
    response = client.post("/run/foot", data={'algorithm': 'mld'})
    assert response.status_code == 200
    sleep(0.5)

    # now it should be available
    res = call_url(url, data)
    assert response.status_code == 200

    # and return 3 matched nodes
    nearest = res.json()
    assert nearest['code'] == 'Ok'
    wpts = nearest['waypoints']
    assert len(wpts) == 3

    # start car router with CH-algorithm
    response = client.post("/run/car", data={'algorithm': 'ch'})
    assert response.status_code == 200
    sleep(0.5)

    # now it should be available

    # url and params to call the router
    foot_port = os.environ.get('MODE_CAR_PORT', 5001)
    base_url = f'http://localhost:{foot_port}'
    lat, lon = 9.0, 50.4
    coords = f'{lat},{lon}'
    url = f'{base_url}/nearest/v1/driving/{coords}'
    data = {'number': 3, }

    res = call_url(url, data)
    assert response.status_code == 200

    # and return 3 matched nodes
    nearest = res.json()
    assert nearest['code'] == 'Ok'
    wpts = nearest['waypoints']
    assert len(wpts) == 3


@retry(exceptions=requests.exceptions.ConnectionError, tries=5, delay=0.2, backoff=2)
def call_url(url: str, data: dict):
    res = requests.get(url, params=data)
    return res


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
    fp_osrm = os.path.join(os.path.dirname(__file__), 'data', 'foot')
    remaining_osrm_files = glob.glob(f'{fp_osrm}.osrm*')
    assert not remaining_osrm_files