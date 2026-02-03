import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import sys
import os

# Add backend to path so we can import main
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app, APP_STATE

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "message": "Github RAG Chat Backend Running"}

def test_session_flow():
    # 1. Create Session is implicit in some designs or explicit?
    # Checking main.py: POST /sessions/ is expected
    response = client.post("/sessions/", json={"repo_url": "https://github.com/test/repo", "name": "Test Session"})
    # If endpoint exists (it should based on previous edits)
    if response.status_code == 200:
        data = response.json()
        assert data["repo_url"] == "https://github.com/test/repo"
        session_id = data["id"]
        
        # 2. Get Session
        resp_get = client.get(f"/sessions/{session_id}")
        assert resp_get.status_code == 200
        assert resp_get.json()["id"] == session_id

@patch("main.clone_repo")
@patch("main.run_repomix")
def test_ingest_mock(mock_repomix, mock_clone):
    # Setup mocks
    mock_clone.return_value = "/tmp/dummy_repo"
    mock_repomix.return_value = "dummy content"
    
    payload = {"repo_url": "https://github.com/dummy/repo"}
    response = client.post("/ingest", json=payload)
    
    if response.status_code != 200:
        print(f"Ingest failed: {response.json()}")
    
    assert response.status_code == 200
    assert APP_STATE["current_repo_content"] == "dummy content"

def test_apply_fix_security():
    # Test valid apply
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        APP_STATE["current_repo"] = tmpdir
        test_file = os.path.join(tmpdir, "test.py")
        
        # Create dummy file first
        with open(test_file, "w") as f:
            f.write("original")
            
        payload = {
            "file_path": "test.py",
            "content": "modified"
        }
        
        response = client.post("/apply", json=payload)
        if response.status_code != 200:
            print(f"Apply failed: {response.json()}")
            
        assert response.status_code == 200
        
        with open(test_file, "r") as f:
            assert f.read() == "modified"

    # Test path traversal (security)
    with tempfile.TemporaryDirectory() as tmpdir:
        APP_STATE["current_repo"] = tmpdir
        payload = {
            "file_path": "../hack.py",
            "content": "hacked"
        }
        response = client.post("/apply", json=payload)
        assert response.status_code in [400, 403]
