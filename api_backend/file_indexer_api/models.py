"""
Pydantic models for API request and response structures.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FileRecord(BaseModel):
    """Model for a file record from the database."""

    model_config = ConfigDict(from_attributes=True)

    path: str
    filename: str
    checksum: str | None = None
    modification_datetime: datetime
    file_size: int
    indexed_at: datetime


class SearchRequest(BaseModel):
    """Model for file search requests."""

    filename_pattern: str | None = Field(
        None, description="Pattern to match filenames (supports SQL LIKE patterns)"
    )
    path_pattern: str | None = Field(
        None, description="Pattern to match file paths (supports SQL LIKE patterns)"
    )
    checksum: str | None = Field(None, description="Exact checksum to match")
    has_checksum: bool | None = Field(
        None, description="Filter by whether files have checksums"
    )
    min_size: int | None = Field(None, description="Minimum file size in bytes")
    max_size: int | None = Field(None, description="Maximum file size in bytes")
    modified_after: datetime | None = Field(
        None, description="Files modified after this date"
    )
    modified_before: datetime | None = Field(
        None, description="Files modified before this date"
    )
    limit: int = Field(
        100, ge=1, le=10000, description="Maximum number of results to return"
    )
    offset: int = Field(
        0, ge=0, description="Number of results to skip (for pagination)"
    )


class SearchResponse(BaseModel):
    """Model for search response."""

    files: list[FileRecord]
    total_count: int
    has_more: bool


class DuplicateGroup(BaseModel):
    """Model for a group of duplicate files."""

    checksum: str
    file_size: int
    file_count: int
    files: list[FileRecord]


class DuplicatesResponse(BaseModel):
    """Model for duplicates response."""

    duplicate_groups: list[DuplicateGroup]
    total_groups: int
    total_duplicate_files: int


class DatabaseStats(BaseModel):
    """Model for database statistics."""

    total_files: int
    total_size: int
    files_with_checksums: int
    files_without_checksums: int
    duplicate_files: int
    duplicate_groups: int
    average_file_size: float
    largest_file_size: int
    smallest_file_size: int
    most_recent_modification: datetime | None
    oldest_modification: datetime | None
    unique_directories: int


class SizeDistribution(BaseModel):
    """Model for file size distribution."""

    size_range: str
    count: int
    total_size: int


class ExtensionStats(BaseModel):
    """Model for file extension statistics."""

    extension: str
    count: int
    total_size: int
    average_size: float


class VisualizationData(BaseModel):
    """Model for visualization data."""

    size_distribution: list[SizeDistribution]
    extension_stats: list[ExtensionStats]
    modification_timeline: list[dict[str, Any]]


class HealthCheck(BaseModel):
    """Model for health check response."""

    status: str
    database_connected: bool
    database_path: str | None
    total_files: int
    api_version: str


class ErrorResponse(BaseModel):
    """Model for error responses."""

    error: str
    detail: str | None = None
