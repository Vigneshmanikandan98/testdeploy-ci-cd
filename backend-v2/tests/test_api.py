from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_projects_shape():
    res = client.get("/api/projects")
    assert res.status_code == 200
    projects = res.json()
    assert len(projects) > 0
    for p in projects:
        assert {"id", "name", "owner", "hours"} <= p.keys()
        assert p["hours"] >= 0


def test_unknown_api_route_is_404_not_the_react_page():
    res = client.get("/api/does-not-exist")
    assert res.status_code == 404
