"""
Database service layer for querying the file index DuckDB database.
"""

import logging
from pathlib import Path
from typing import Any

import duckdb

from .models import (
    DatabaseStats,
    DuplicateGroup,
    DuplicatesRequest,
    ExtensionStats,
    FileRecord,
    SearchRequest,
    SizeDistribution,
    VisualizationData,
)

logger = logging.getLogger(__name__)


class DatabaseService:
    """Service for interacting with the DuckDB file index database."""

    def __init__(self, db_path: str):
        """Initialize the database service.

        Args:
            db_path: Path to the DuckDB database file
        """
        self.db_path = db_path
        self.conn: duckdb.DuckDBPyConnection | None = None

    def connect(self) -> None:
        """Connect to the database."""
        if not Path(self.db_path).exists():
            raise FileNotFoundError(f"Database file not found: {self.db_path}")

        self.conn = duckdb.connect(self.db_path, read_only=True)
        logger.info(f"Connected to database: {self.db_path}")

    def disconnect(self) -> None:
        """Disconnect from the database."""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("Disconnected from database")

    def is_connected(self) -> bool:
        """Check if connected to database."""
        return self.conn is not None

    def search_files(
        self, search_request: SearchRequest
    ) -> tuple[list[FileRecord], int]:
        """Search for files based on criteria.

        Args:
            search_request: Search parameters

        Returns:
            Tuple of (file_records, total_count)
        """
        if not self.conn:
            raise RuntimeError("Database not connected")

        # Build the base query
        conditions = []
        params: list[Any] = []

        if search_request.filename_pattern:
            conditions.append("filename LIKE ?")
            params.append(search_request.filename_pattern)

        if search_request.path_pattern:
            conditions.append("path LIKE ?")
            params.append(search_request.path_pattern)

        if search_request.checksum:
            conditions.append("checksum = ?")
            params.append(search_request.checksum)

        if search_request.has_checksum is not None:
            if search_request.has_checksum:
                conditions.append("checksum IS NOT NULL")
            else:
                conditions.append("checksum IS NULL")

        if search_request.min_size is not None:
            conditions.append("file_size >= ?")
            params.append(search_request.min_size)

        if search_request.max_size is not None:
            conditions.append("file_size <= ?")
            params.append(search_request.max_size)

        if search_request.modified_after:
            conditions.append("modification_datetime >= ?")
            params.append(search_request.modified_after)

        if search_request.modified_before:
            conditions.append("modification_datetime <= ?")
            params.append(search_request.modified_before)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # Get total count
        count_query = f"SELECT COUNT(*) FROM files WHERE {where_clause}"
        count_result = self.conn.execute(count_query, params).fetchone()
        if count_result is None:
            raise RuntimeError("Failed to get count from database")
        total_count = count_result[0]

        # Get the actual results with pagination
        data_query = f"""
        SELECT path, filename, checksum, modification_datetime, file_size, indexed_at
        FROM files
        WHERE {where_clause}
        ORDER BY modification_datetime DESC, path, filename
        LIMIT ? OFFSET ?
        """

        results = self.conn.execute(
            data_query, params + [search_request.limit, search_request.offset]
        ).fetchall()

        files = [
            FileRecord(
                path=row[0],
                filename=row[1],
                checksum=row[2],
                modification_datetime=row[3],
                file_size=row[4],
                indexed_at=row[5],
            )
            for row in results
        ]

        return files, total_count

    def find_duplicates(
        self,
        min_group_size: int = 2,
        min_file_size: int | None = None,
        max_file_size: int | None = None,
        filename_pattern: str | None = None,
        path_pattern: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> tuple[list[DuplicateGroup], int]:
        """Find duplicate files grouped by checksum with pagination and filtering.

        Args:
            min_group_size: Minimum number of files in a group to be considered duplicates
            min_file_size: Minimum file size in bytes (optional)
            max_file_size: Maximum file size in bytes (optional)
            filename_pattern: Pattern to match filenames (optional). Finds duplicates of files matching this pattern.
            path_pattern: Pattern to match file paths (optional). Finds duplicates of files matching this pattern.
            limit: Maximum number of groups to return (optional)
            offset: Number of groups to skip for pagination

        Returns:
            Tuple of (duplicate_groups, total_groups_count)
        """
        if not self.conn:
            raise RuntimeError("Database not connected")

        # If filename or path patterns are provided, use the pattern-based approach
        if filename_pattern or path_pattern:
            return self._find_duplicates_by_pattern(
                min_group_size,
                min_file_size,
                max_file_size,
                filename_pattern,
                path_pattern,
                limit,
                offset,
            )

        # Otherwise, use the original size-based filtering approach
        return self._find_duplicates_by_size(
            min_group_size, min_file_size, max_file_size, limit, offset
        )

    def _find_duplicates_by_pattern(
        self,
        min_group_size: int,
        min_file_size: int | None,
        max_file_size: int | None,
        filename_pattern: str | None,
        path_pattern: str | None,
        limit: int | None,
        offset: int,
    ) -> tuple[list[DuplicateGroup], int]:
        """Find duplicates by first filtering files by name/path patterns, then finding all duplicates of those files."""
        assert self.conn is not None  # Ensure connection is available

        # Step 1: Find files matching the filename/path patterns
        pattern_conditions = []
        pattern_params: list[Any] = []

        if filename_pattern:
            pattern_conditions.append("filename LIKE ?")
            pattern_params.append(filename_pattern)

        if path_pattern:
            pattern_conditions.append("path LIKE ?")
            pattern_params.append(path_pattern)

        # Add size filters to the pattern matching
        if min_file_size is not None:
            pattern_conditions.append("file_size >= ?")
            pattern_params.append(min_file_size)

        if max_file_size is not None:
            pattern_conditions.append("file_size <= ?")
            pattern_params.append(max_file_size)

        pattern_filter = (
            " AND ".join(pattern_conditions) if pattern_conditions else "1=1"
        )

        # Step 2: Get checksums of files matching the pattern
        checksums_query = f"""
        SELECT DISTINCT checksum
        FROM files
        WHERE checksum IS NOT NULL
        AND {pattern_filter}
        """

        checksum_results = self.conn.execute(checksums_query, pattern_params).fetchall()
        target_checksums = [row[0] for row in checksum_results]

        if not target_checksums:
            return [], 0

        # Step 3: Find ALL files with those checksums (across entire database)
        checksum_placeholders = ",".join("?" * len(target_checksums))

        # Count total groups
        count_query = f"""
        SELECT COUNT(DISTINCT checksum)
        FROM files
        WHERE checksum IN ({checksum_placeholders})
        AND checksum IN (
            SELECT checksum
            FROM files
            WHERE checksum IN ({checksum_placeholders})
            GROUP BY checksum
            HAVING COUNT(*) >= ?
        )
        """

        count_result = self.conn.execute(
            count_query, target_checksums + target_checksums + [min_group_size]
        ).fetchone()
        if count_result is None:
            raise RuntimeError("Failed to get count from database")
        total_groups = count_result[0]

        # Get paginated results
        pagination_clause = ""
        pagination_params: list[Any] = []
        if limit is not None:
            pagination_clause = "LIMIT ? OFFSET ?"
            pagination_params = [limit, offset]

        # Step 4: Get all duplicate groups with those checksums
        query = f"""
        WITH target_duplicate_checksums AS (
            SELECT checksum, file_size, COUNT(*) as file_count
            FROM files
            WHERE checksum IN ({checksum_placeholders})
            GROUP BY checksum, file_size
            HAVING COUNT(*) >= ?
            ORDER BY COUNT(*) DESC, file_size DESC
            {pagination_clause}
        )
        SELECT
            f.checksum,
            f.file_size,
            tdc.file_count,
            f.path,
            f.filename,
            f.modification_datetime,
            f.indexed_at
        FROM files f
        JOIN target_duplicate_checksums tdc ON f.checksum = tdc.checksum AND f.file_size = tdc.file_size
        ORDER BY tdc.file_count DESC, f.checksum, f.path, f.filename
        """

        results = self.conn.execute(
            query, target_checksums + [min_group_size] + pagination_params
        ).fetchall()

        return self._group_duplicate_results(results), total_groups

    def _find_duplicates_by_size(
        self,
        min_group_size: int,
        min_file_size: int | None,
        max_file_size: int | None,
        limit: int | None,
        offset: int,
    ) -> tuple[list[DuplicateGroup], int]:
        """Find duplicates using the original size-based filtering approach."""
        assert self.conn is not None  # Ensure connection is available

        # Build conditions for file size filtering
        size_conditions = []
        size_params: list[Any] = []

        if min_file_size is not None:
            size_conditions.append("file_size >= ?")
            size_params.append(min_file_size)

        if max_file_size is not None:
            size_conditions.append("file_size <= ?")
            size_params.append(max_file_size)

        size_filter = f"AND {' AND '.join(size_conditions)}" if size_conditions else ""

        # First, get the total count of duplicate groups
        count_query = f"""
        SELECT COUNT(DISTINCT checksum)
        FROM files
        WHERE checksum IS NOT NULL
        {size_filter}
        AND checksum IN (
            SELECT checksum
            FROM files
            WHERE checksum IS NOT NULL {size_filter}
            GROUP BY checksum
            HAVING COUNT(*) >= ?
        )
        """

        count_result = self.conn.execute(
            count_query, size_params + [min_group_size]
        ).fetchone()
        if count_result is None:
            raise RuntimeError("Failed to get count from database")
        total_groups = count_result[0]

        # Then get the duplicate groups with pagination
        pagination_clause = ""
        pagination_params: list[Any] = []
        if limit is not None:
            pagination_clause = "LIMIT ? OFFSET ?"
            pagination_params = [limit, offset]

        query = f"""
        WITH duplicate_checksums AS (
            SELECT checksum, file_size, COUNT(*) as file_count
            FROM files
            WHERE checksum IS NOT NULL {size_filter}
            GROUP BY checksum, file_size
            HAVING COUNT(*) >= ?
            ORDER BY COUNT(*) DESC, file_size DESC
            {pagination_clause}
        )
        SELECT
            f.checksum,
            f.file_size,
            dc.file_count,
            f.path,
            f.filename,
            f.modification_datetime,
            f.indexed_at
        FROM files f
        JOIN duplicate_checksums dc ON f.checksum = dc.checksum AND f.file_size = dc.file_size
        ORDER BY dc.file_count DESC, f.checksum, f.path, f.filename
        """

        results = self.conn.execute(
            query, size_params + [min_group_size] + pagination_params
        ).fetchall()

        return self._group_duplicate_results(results), total_groups

    def _group_duplicate_results(self, results: list[Any]) -> list[DuplicateGroup]:
        """Group database results into DuplicateGroup objects."""
        groups_dict: dict[str, DuplicateGroup] = {}

        for row in results:
            checksum = row[0]
            file_size = row[1]
            file_count = row[2]

            if checksum not in groups_dict:
                wasted_space = file_size * (
                    file_count - 1
                )  # Total wasted space for this group
                groups_dict[checksum] = DuplicateGroup(
                    checksum=checksum,
                    file_size=file_size,
                    file_count=file_count,
                    files=[],
                    wasted_space=wasted_space,
                )

            groups_dict[checksum].files.append(
                FileRecord(
                    path=row[3],
                    filename=row[4],
                    checksum=checksum,
                    modification_datetime=row[5],
                    file_size=file_size,
                    indexed_at=row[6],
                )
            )

        return list(groups_dict.values())

    def find_duplicates_with_request(
        self, request: DuplicatesRequest
    ) -> tuple[list[DuplicateGroup], int]:
        """Find duplicates using a DuplicatesRequest object."""
        return self.find_duplicates(
            min_group_size=request.min_group_size,
            min_file_size=request.min_file_size,
            max_file_size=request.max_file_size,
            filename_pattern=request.filename_pattern,
            path_pattern=request.path_pattern,
            limit=request.limit,
            offset=request.offset,
        )

    def get_database_stats(self) -> DatabaseStats:
        """Get comprehensive database statistics."""
        if not self.conn:
            raise RuntimeError("Database not connected")

        # Basic counts and sizes
        basic_stats_result = self.conn.execute("""
        SELECT
            COUNT(*) as total_files,
            COALESCE(SUM(file_size), 0) as total_size,
            COUNT(checksum) as files_with_checksums,
            COUNT(*) - COUNT(checksum) as files_without_checksums,
            COALESCE(AVG(file_size), 0) as average_file_size,
            COALESCE(MAX(file_size), 0) as largest_file_size,
            COALESCE(MIN(file_size), 0) as smallest_file_size,
            MAX(modification_datetime) as most_recent_modification,
            MIN(modification_datetime) as oldest_modification
        FROM files
        """).fetchone()
        
        if basic_stats_result is None:
            raise RuntimeError("Failed to get basic stats from database")

        # Duplicate statistics
        duplicate_stats_result = self.conn.execute("""
        WITH duplicate_checksums AS (
            SELECT checksum, COUNT(*) as file_count
            FROM files
            WHERE checksum IS NOT NULL
            GROUP BY checksum
            HAVING COUNT(*) > 1
        )
        SELECT
            COUNT(*) as duplicate_groups,
            COALESCE(SUM(file_count), 0) as duplicate_files
        FROM duplicate_checksums
        """).fetchone()
        
        if duplicate_stats_result is None:
            raise RuntimeError("Failed to get duplicate stats from database")

        # Unique directories
        unique_dirs_result = self.conn.execute("""
        SELECT COUNT(DISTINCT path) FROM files
        """).fetchone()
        
        if unique_dirs_result is None:
            raise RuntimeError("Failed to get unique directories from database")

        return DatabaseStats(
            total_files=basic_stats_result[0],
            total_size=basic_stats_result[1],
            files_with_checksums=basic_stats_result[2],
            files_without_checksums=basic_stats_result[3],
            duplicate_files=duplicate_stats_result[1] or 0,
            duplicate_groups=duplicate_stats_result[0] or 0,
            average_file_size=basic_stats_result[4],
            largest_file_size=basic_stats_result[5],
            smallest_file_size=basic_stats_result[6],
            most_recent_modification=basic_stats_result[7],
            oldest_modification=basic_stats_result[8],
            unique_directories=unique_dirs_result[0],
        )

    def get_visualization_data(self) -> VisualizationData:
        """Get data for visualization charts."""
        if not self.conn:
            raise RuntimeError("Database not connected")

        # File size distribution
        size_distribution = self.conn.execute("""
        SELECT
            size_range,
            COUNT(*) as count,
            SUM(file_size) as total_size
        FROM (
            SELECT
                file_size,
                CASE
                    WHEN file_size = 0 THEN '0 bytes'
                    WHEN file_size < 1024 THEN '< 1KB'
                    WHEN file_size < 1024*1024 THEN '1KB - 1MB'
                    WHEN file_size < 1024*1024*1024 THEN '1MB - 1GB'
                    ELSE '> 1GB'
                END as size_range,
                CASE
                    WHEN file_size = 0 THEN 1
                    WHEN file_size < 1024 THEN 2
                    WHEN file_size < 1024*1024 THEN 3
                    WHEN file_size < 1024*1024*1024 THEN 4
                    ELSE 5
                END as sort_order
            FROM files
        ) subquery
        GROUP BY size_range, sort_order
        ORDER BY sort_order
        """).fetchall()

        # File extension statistics
        extension_stats = self.conn.execute("""
        WITH extensions AS (
            SELECT
                CASE
                    WHEN filename LIKE '%.%' THEN
                        LOWER(SUBSTR(filename, LENGTH(filename) - LENGTH(REVERSE(SUBSTR(REVERSE(filename), 1, STRPOS(REVERSE(filename), '.') - 1))) + 1))
                    ELSE '(no extension)'
                END as extension,
                file_size
            FROM files
        )
        SELECT
            extension,
            COUNT(*) as count,
            SUM(file_size) as total_size,
            AVG(file_size) as average_size
        FROM extensions
        GROUP BY extension
        ORDER BY count DESC
        LIMIT 20
        """).fetchall()

        # Modification timeline (files per month for last 12 months)
        timeline = self.conn.execute("""
        SELECT
            DATE_TRUNC('month', modification_datetime) as month,
            COUNT(*) as count,
            SUM(file_size) as total_size
        FROM files
        WHERE modification_datetime >= CURRENT_DATE - INTERVAL '12 months'
        GROUP BY DATE_TRUNC('month', modification_datetime)
        ORDER BY month
        """).fetchall()

        return VisualizationData(
            size_distribution=[
                SizeDistribution(size_range=row[0], count=row[1], total_size=row[2])
                for row in size_distribution
            ],
            extension_stats=[
                ExtensionStats(
                    extension=row[0],
                    count=row[1],
                    total_size=row[2],
                    average_size=row[3],
                )
                for row in extension_stats
            ],
            modification_timeline=[
                {
                    "month": row[0].isoformat() if row[0] else None,
                    "count": row[1],
                    "total_size": row[2],
                }
                for row in timeline
            ],
        )

    def get_file_count(self) -> int:
        """Get total number of files in the database."""
        if not self.conn:
            raise RuntimeError("Database not connected")

        count_result = self.conn.execute("SELECT COUNT(*) FROM files").fetchone()
        if count_result is None:
            raise RuntimeError("Failed to get file count from database")
        return int(count_result[0])
