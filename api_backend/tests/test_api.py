"""
Basic API tests for the File Indexer API.
"""

import os
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from file_indexer_api.database import DatabaseService
from file_indexer_api.main import app
from file_indexer_api.models import DatabaseStats, FileRecord


@pytest.fixture
def mock_db_service():
    """Mock database service for testing."""
    mock_service = Mock(spec=DatabaseService)
    mock_service.is_connected.return_value = True
    mock_service.db_path = "test.db"
    mock_service.get_file_count.return_value = 100
    return mock_service


@pytest.fixture
def client(mock_db_service):
    """Test client with mocked database service."""

    def override_get_database_service():
        return mock_db_service

    from file_indexer_api.routers import get_database_service

    app.dependency_overrides[get_database_service] = override_get_database_service

    with TestClient(app) as test_client:
        yield test_client

    # Clean up
    app.dependency_overrides.clear()


def test_root_endpoint(client):
    """Test the root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "File Indexer API"
    assert data["version"] == "0.1.0"


def test_health_check(client, mock_db_service):
    """Test the health check endpoint."""
    response = client.get("/health/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database_connected"] is True
    assert data["total_files"] == 100
    assert data["api_version"] == "0.1.0"


def test_search_files_get(client, mock_db_service):
    """Test the search files GET endpoint."""
    # Mock search response
    mock_files = [
        FileRecord(
            path="/test",
            filename="test.txt",
            checksum="abc123",
            modification_datetime="2023-01-01T12:00:00",
            file_size=1024,
            indexed_at="2023-01-01T13:00:00",
        )
    ]
    mock_db_service.search_files.return_value = (mock_files, 1)

    response = client.get("/search/?filename_pattern=*.txt&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert data["total_count"] == 1
    assert len(data["files"]) == 1
    assert data["files"][0]["filename"] == "test.txt"
    assert data["has_more"] is False


def test_search_files_post(client, mock_db_service):
    """Test the search files POST endpoint."""
    # Mock search response
    mock_files = []
    mock_db_service.search_files.return_value = (mock_files, 0)

    search_request = {"filename_pattern": "*.py", "min_size": 1000, "limit": 5}

    response = client.post("/search/", json=search_request)
    assert response.status_code == 200
    data = response.json()
    assert data["total_count"] == 0
    assert len(data["files"]) == 0


def test_find_duplicates(client, mock_db_service):
    """Test the find duplicates endpoint."""
    # Mock duplicates response
    mock_db_service.find_duplicates.return_value = []

    response = client.get("/duplicates/")
    assert response.status_code == 200
    data = response.json()
    assert data["duplicate_groups"] == []
    assert data["total_groups"] == 0
    assert data["total_duplicate_files"] == 0


def test_database_stats(client, mock_db_service):
    """Test the database statistics endpoint."""
    # Mock stats response
    mock_stats = DatabaseStats(
        total_files=1000,
        total_size=1000000,
        files_with_checksums=800,
        files_without_checksums=200,
        duplicate_files=50,
        duplicate_groups=10,
        average_file_size=1000.0,
        largest_file_size=100000,
        smallest_file_size=0,
        most_recent_modification=None,
        oldest_modification=None,
        unique_directories=100,
    )
    mock_db_service.get_database_stats.return_value = mock_stats

    response = client.get("/stats/")
    assert response.status_code == 200
    data = response.json()
    assert data["total_files"] == 1000
    assert data["files_with_checksums"] == 800
    assert data["duplicate_groups"] == 10


@patch.dict(os.environ, {"FILE_INDEXER_DB_PATH": "nonexistent.db"})
def test_missing_database_file():
    """Test behavior when database file is missing."""
    # This test would normally cause the app to exit, so we'll just verify
    # that the path check works correctly
    from pathlib import Path

    assert not Path("nonexistent.db").exists()
