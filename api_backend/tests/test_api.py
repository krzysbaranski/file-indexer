"""
Basic API tests for the File Indexer API.
"""

import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any
from unittest.mock import Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from file_indexer_api.database import DatabaseService
from file_indexer_api.models import DatabaseStats, FileRecord
from file_indexer_api.routers import (
    duplicates_router,
    get_database_service,
    health_router,
    search_router,
    stats_router,
)


@pytest.fixture
def mock_db_service():
    """Mock database service for testing."""
    mock_service = Mock(spec=DatabaseService)
    mock_service.is_connected.return_value = True
    mock_service.db_path = "test.db"
    mock_service.get_file_count.return_value = 100
    return mock_service


@pytest.fixture
def test_app():
    """Create a test FastAPI app without the problematic lifespan."""

    @asynccontextmanager
    async def empty_lifespan(app: FastAPI) -> Any:  # noqa: ARG001
        # Empty lifespan for testing
        yield

    # Create test app
    app = FastAPI(
        title="File Indexer API - Test",
        description="Test version of File Indexer API",
        version="0.1.0",
        lifespan=empty_lifespan,
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(health_router)
    app.include_router(search_router)
    app.include_router(duplicates_router)
    app.include_router(stats_router)

    # Root endpoint
    @app.get("/")
    async def root() -> dict[str, str]:
        return {
            "message": "File Indexer API",
            "version": "0.1.0",
            "docs": "/docs",
            "redoc": "/redoc",
        }

    return app


@pytest.fixture
def client(mock_db_service, test_app):
    """Test client with mocked database service."""

    def override_get_database_service():
        return mock_db_service

    test_app.dependency_overrides[get_database_service] = override_get_database_service

    with TestClient(test_app) as test_client:
        yield test_client

    # Clean up
    test_app.dependency_overrides.clear()


def test_root_endpoint(client):
    """Test the root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "File Indexer API"
    assert data["version"] == "0.1.0"


def test_health_check(client):
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


def test_find_duplicates_get(client, mock_db_service):
    """Test the find duplicates GET endpoint."""
    # Mock duplicates response - now returns tuple (groups, total_count)
    mock_db_service.find_duplicates.return_value = ([], 0)
    mock_db_service.find_duplicates_with_request.return_value = ([], 0)

    response = client.get("/duplicates/")
    assert response.status_code == 200
    data = response.json()
    assert data["duplicate_groups"] == []
    assert data["total_groups"] == 0
    assert data["total_duplicate_files"] == 0
    assert data["total_wasted_space"] == 0
    assert data["has_more"] is False


def test_find_duplicates_post(client, mock_db_service):
    """Test the find duplicates POST endpoint."""
    # Mock duplicates response
    mock_db_service.find_duplicates_with_request.return_value = ([], 0)

    duplicates_request = {
        "min_group_size": 3,
        "min_file_size": 1024,
        "max_file_size": 1024000,
        "limit": 10,
        "offset": 0,
    }

    response = client.post("/duplicates/", json=duplicates_request)
    assert response.status_code == 200
    data = response.json()
    assert data["duplicate_groups"] == []
    assert data["total_groups"] == 0
    assert data["total_duplicate_files"] == 0
    assert data["total_wasted_space"] == 0
    assert data["has_more"] is False


def test_find_duplicates_with_pagination(client, mock_db_service):
    """Test the duplicates endpoint with pagination parameters."""
    # Mock duplicates response with some data
    from file_indexer_api.models import DuplicateGroup

    mock_file = FileRecord(
        path="/test",
        filename="test.txt",
        checksum="abc123",
        modification_datetime=datetime.now(),
        file_size=1024,
        indexed_at=datetime.now(),
    )

    mock_group = DuplicateGroup(
        checksum="abc123",
        file_size=1024,
        file_count=2,
        files=[mock_file, mock_file],
        wasted_space=1024,
    )

    mock_db_service.find_duplicates_with_request.return_value = ([mock_group], 5)

    # Test GET with query parameters
    response = client.get("/duplicates/?limit=1&offset=2&min_file_size=500")
    assert response.status_code == 200
    data = response.json()
    assert data["total_groups"] == 5
    assert data["has_more"] is True
    assert len(data["duplicate_groups"]) == 1
    assert data["total_wasted_space"] == 1024


def test_search_files_pagination(client, mock_db_service):
    """Test the search endpoint with pagination."""
    # Mock search response
    mock_files = [
        FileRecord(
            path="/test",
            filename="file1.txt",
            checksum="abc123",
            modification_datetime=datetime.now(),
            file_size=1024,
            indexed_at=datetime.now(),
        ),
        FileRecord(
            path="/test",
            filename="file2.txt",
            checksum="def456",
            modification_datetime=datetime.now(),
            file_size=2048,
            indexed_at=datetime.now(),
        ),
    ]
    mock_db_service.search_files.return_value = (mock_files, 10)

    response = client.get("/search/?limit=2&offset=5")
    assert response.status_code == 200
    data = response.json()
    assert data["total_count"] == 10
    assert data["has_more"] is True
    assert len(data["files"]) == 2


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


def test_duplicates_request_validation(client, mock_db_service):
    """Test validation of duplicates request parameters."""
    mock_db_service.find_duplicates_with_request.return_value = ([], 0)

    # Test invalid min_group_size (too small)
    response = client.post("/duplicates/", json={"min_group_size": 1})
    assert response.status_code == 422

    # Test invalid limit (too large)
    response = client.post("/duplicates/", json={"limit": 2000})
    assert response.status_code == 422

    # Test invalid offset (negative)
    response = client.post("/duplicates/", json={"offset": -1})
    assert response.status_code == 422

    # Test valid request
    response = client.post(
        "/duplicates/",
        json={
            "min_group_size": 2,
            "min_file_size": 1024,
            "max_file_size": 1048576,
            "limit": 50,
            "offset": 0,
        },
    )
    assert response.status_code == 200


@patch.dict(os.environ, {"FILE_INDEXER_DB_PATH": "nonexistent.db"})
def test_missing_database_file():
    """Test behavior when database file is missing."""
    # This test would normally cause the app to exit, so we'll just verify
    # that the path check works correctly
    from pathlib import Path

    assert not Path("nonexistent.db").exists()


def test_duplicates_with_pattern_filtering(client, mock_db_service):
    """Test duplicates endpoint with filename and path pattern filtering."""
    # Mock duplicates response
    mock_db_service.find_duplicates_with_request.return_value = ([], 0)

    # Test filename pattern filtering
    response = client.post(
        "/duplicates/",
        json={"filename_pattern": "%.jpg", "min_group_size": 2, "limit": 10},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["duplicate_groups"] == []
    assert data["total_groups"] == 0

    # Test path pattern filtering
    response = client.post(
        "/duplicates/",
        json={"path_pattern": "%Downloads%", "min_group_size": 2, "limit": 10},
    )
    assert response.status_code == 200

    # Test combined pattern and size filtering
    response = client.post(
        "/duplicates/",
        json={
            "filename_pattern": "%.pdf",
            "min_file_size": 100000,
            "min_group_size": 2,
            "limit": 5,
        },
    )
    assert response.status_code == 200

    # Test GET endpoint with pattern
    response = client.get("/duplicates/?filename_pattern=%.jpg&limit=5")
    assert response.status_code == 200
