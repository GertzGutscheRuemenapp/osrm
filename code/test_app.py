import os
import pytest
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


def test_build(client):
    fp = os.path.join(os.path.dirname(__file__), 'testdata', 'network.pbf')
    files = {'file': open(fp, 'rb')}

    response = client.post("/build/velocopter", data={'files': files})
    assert response.status_code == 400

    response = client.post("/build/foot", data=files)
    assert response.status_code == 200
