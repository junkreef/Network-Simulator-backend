import os
import sys
import pytest
import docker
from fastapi.testclient import TestClient

# Add src to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from app.main import app

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

@pytest.fixture(scope="session", autouse=True)
def build_docker_images():
    """Build the test Docker images if docker is available."""
    try:
        client = docker.from_env()
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        router_path = os.path.join(base_dir, "docker", "router")
        print("Building alpine-frr:latest...")
        client.images.build(path=router_path, tag="alpine-frr:latest", rm=True)
        
        terminal_path = os.path.join(base_dir, "docker", "terminal")
        print("Building alpine-terminal:latest...")
        client.images.build(path=terminal_path, tag="alpine-terminal:latest", rm=True)

        switch_path = os.path.join(base_dir, "docker", "switch")
        print("Building alpine-switch:latest...")
        client.images.build(path=switch_path, tag="alpine-switch:latest", rm=True)
    except Exception as e:
        print(f"Could not build Docker images (Docker may not be running): {e}")

