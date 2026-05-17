import pytest
from fastapi.testclient import TestClient
import sys
import os

# Add parent directory to path to import backend_server
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend_server import app

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["message"] == "Trading Backend API is running"

def test_get_positions_structure():
    response = client.get("/api/positions")
    assert response.status_code == 200
    data = response.json()
    assert "tastytrade" in data
    assert "alpaca_live" in data
    assert "positions" in data["tastytrade"]
    assert isinstance(data["tastytrade"]["positions"], list)
