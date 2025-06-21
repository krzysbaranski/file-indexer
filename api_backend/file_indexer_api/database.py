"""
Database service layer for querying the file index DuckDB database.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import duckdb

from .models import (
    DatabaseStats,
    DuplicateGroup,
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
        self.conn: Optional[duckdb.DuckDBPyConnection] = None

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
        params = []

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
        total_count = self.conn.execute(count_query, params).fetchone()[0]

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

    def find_duplicates(self, min_group_size: int = 2) -> list[DuplicateGroup]:
        """Find duplicate files grouped by checksum.

        Args:
            min_group_size: Minimum number of files in a group to be considered duplicates

        Returns:
            List of duplicate groups
        """
        if not self.conn:
            raise RuntimeError("Database not connected")

        query = """
        WITH duplicate_checksums AS (
            SELECT checksum, file_size, COUNT(*) as file_count
            FROM files 
            WHERE checksum IS NOT NULL
            GROUP BY checksum, file_size
            HAVING COUNT(*) >= ?
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

        results = self.conn.execute(query, [min_group_size]).fetchall()

        # Group results by checksum
        groups_dict: dict[str, DuplicateGroup] = {}

        for row in results:
            checksum = row[0]
            if checksum not in groups_dict:
                groups_dict[checksum] = DuplicateGroup(
                    checksum=checksum, file_size=row[1], file_count=row[2], files=[]
                )

            groups_dict[checksum].files.append(
                FileRecord(
                    path=row[3],
                    filename=row[4],
                    checksum=checksum,
                    modification_datetime=row[5],
                    file_size=row[1],
                    indexed_at=row[6],
                )
            )

        return list(groups_dict.values())

    def get_database_stats(self) -> DatabaseStats:
        """Get comprehensive database statistics."""
        if not self.conn:
            raise RuntimeError("Database not connected")

        # Basic counts and sizes
        basic_stats = self.conn.execute("""
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

        # Duplicate statistics
        duplicate_stats = self.conn.execute("""
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

        # Unique directories
        unique_dirs = self.conn.execute("""
        SELECT COUNT(DISTINCT path) FROM files
        """).fetchone()[0]

        return DatabaseStats(
            total_files=basic_stats[0],
            total_size=basic_stats[1],
            files_with_checksums=basic_stats[2],
            files_without_checksums=basic_stats[3],
            duplicate_files=duplicate_stats[1] or 0,
            duplicate_groups=duplicate_stats[0] or 0,
            average_file_size=basic_stats[4],
            largest_file_size=basic_stats[5],
            smallest_file_size=basic_stats[6],
            most_recent_modification=basic_stats[7],
            oldest_modification=basic_stats[8],
            unique_directories=unique_dirs,
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

        return self.conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
