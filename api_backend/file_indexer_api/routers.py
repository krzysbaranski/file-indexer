"""
FastAPI routers for different API endpoints.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from .database import DatabaseService
from .models import (
    DatabaseStats,
    DuplicatesResponse,
    ErrorResponse,
    HealthCheck,
    SearchRequest,
    SearchResponse,
    VisualizationData,
)

logger = logging.getLogger(__name__)


def get_database_service() -> DatabaseService:
    """Dependency to get database service instance."""
    # This will be overridden by the main app to provide the actual service
    raise NotImplementedError("Database service not configured")


# Health and status router
health_router = APIRouter(prefix="/health", tags=["Health"])


@health_router.get("/", response_model=HealthCheck)
async def health_check(db: Annotated[DatabaseService, Depends(get_database_service)]):
    """Health check endpoint."""
    try:
        file_count = db.get_file_count() if db.is_connected() else 0
        return HealthCheck(
            status="healthy" if db.is_connected() else "unhealthy",
            database_connected=db.is_connected(),
            database_path=db.db_path,
            total_files=file_count,
            api_version="0.1.0",
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthCheck(
            status="unhealthy",
            database_connected=False,
            database_path=db.db_path,
            total_files=0,
            api_version="0.1.0",
        )


# Search router
search_router = APIRouter(prefix="/search", tags=["Search"])


@search_router.post(
    "/", response_model=SearchResponse, responses={400: {"model": ErrorResponse}}
)
async def search_files(
    search_request: SearchRequest,
    db: Annotated[DatabaseService, Depends(get_database_service)],
):
    """Search for files based on various criteria."""
    try:
        files, total_count = db.search_files(search_request)
        has_more = (search_request.offset + len(files)) < total_count

        return SearchResponse(files=files, total_count=total_count, has_more=has_more)
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@search_router.get(
    "/", response_model=SearchResponse, responses={400: {"model": ErrorResponse}}
)
async def search_files_get(
    db: Annotated[DatabaseService, Depends(get_database_service)],
    filename_pattern: str | None = Query(
        None, description="Pattern to match filenames"
    ),
    path_pattern: str | None = Query(None, description="Pattern to match file paths"),
    checksum: str | None = Query(None, description="Exact checksum to match"),
    has_checksum: bool | None = Query(
        None, description="Filter by whether files have checksums"
    ),
    min_size: int | None = Query(None, description="Minimum file size in bytes"),
    max_size: int | None = Query(None, description="Maximum file size in bytes"),
    limit: int = Query(100, ge=1, le=10000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
):
    """Search for files using GET parameters."""
    search_request = SearchRequest(
        filename_pattern=filename_pattern,
        path_pattern=path_pattern,
        checksum=checksum,
        has_checksum=has_checksum,
        min_size=min_size,
        max_size=max_size,
        limit=limit,
        offset=offset,
    )

    return await search_files(search_request, db)


# Duplicates router
duplicates_router = APIRouter(prefix="/duplicates", tags=["Duplicates"])


@duplicates_router.get("/", response_model=DuplicatesResponse)
async def find_duplicates(
    db: Annotated[DatabaseService, Depends(get_database_service)],
    min_group_size: int = Query(
        2, ge=2, description="Minimum number of files in a group"
    ),
):
    """Find duplicate files grouped by checksum."""
    try:
        duplicate_groups = db.find_duplicates(min_group_size)
        total_duplicate_files = sum(group.file_count for group in duplicate_groups)

        return DuplicatesResponse(
            duplicate_groups=duplicate_groups,
            total_groups=len(duplicate_groups),
            total_duplicate_files=total_duplicate_files,
        )
    except Exception as e:
        logger.error(f"Finding duplicates failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


# Statistics router
stats_router = APIRouter(prefix="/stats", tags=["Statistics"])


@stats_router.get("/", response_model=DatabaseStats)
async def get_database_stats(
    db: Annotated[DatabaseService, Depends(get_database_service)],
):
    """Get comprehensive database statistics."""
    try:
        return db.get_database_stats()
    except Exception as e:
        logger.error(f"Getting stats failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@stats_router.get("/visualization", response_model=VisualizationData)
async def get_visualization_data(
    db: Annotated[DatabaseService, Depends(get_database_service)],
):
    """Get data for visualization charts."""
    try:
        return db.get_visualization_data()
    except Exception as e:
        logger.error(f"Getting visualization data failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
