import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "message": "Tuloy API is running."}

# Skipping DB test by default so it doesn't fail if you aren't running the DB or the tunnel
@pytest.mark.skip(reason="Requires active DB connection")
def test_db_health_check():
    response = client.get("/health/db")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}
