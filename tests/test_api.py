from backend.main import app, health_check, root

def test_root_response():
    response = root()
    assert response["status"] == "running"
    assert response["version"] == app.version
    assert response["docs"] == "/docs"

def test_health_response():
    response = health_check()
    assert response["status"] == "healthy"
    assert response["api"] is True
    assert response["project_root_exists"] is True
