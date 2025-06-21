"""
Core file indexing functionality using DuckDB.
"""

import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb


class FileIndexer:
    def __init__(self, db_path: str = "file_index.db"):
        """
        Initialize the FileIndexer with a DuckDB database.

        Args:
            db_path: Path to the DuckDB database file
        """
        self.db_path = db_path
        self.conn = duckdb.connect(db_path)
        self._create_table()
        # Statistics for optimization tracking
        self.checksum_calculations = 0
        self.checksum_reuses = 0
        self.skipped_files = 0
        self.ignored_symlinks = 0

    def _create_table(self) -> None:
        """Create the files table if it doesn't exist."""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS files (
            path VARCHAR NOT NULL,
            filename VARCHAR NOT NULL,
            checksum VARCHAR NOT NULL,
            modification_datetime TIMESTAMP NOT NULL,
            file_size BIGINT NOT NULL,
            indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (path, filename)
        );
        """
        self.conn.execute(create_table_sql)

        # Create indexes for better performance
        self.conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_checksum ON files(checksum);
        CREATE INDEX IF NOT EXISTS idx_modification_datetime ON files(modification_datetime);
        """)

    def _calculate_checksum(self, file_path: str, algorithm: str = "sha256") -> str:
        """
        Calculate checksum for a file.

        Args:
            file_path: Path to the file
            algorithm: Hash algorithm to use (md5, sha1, sha256)

        Returns:
            Hexadecimal checksum string
        """
        hash_func: Any = getattr(hashlib, algorithm)()

        try:
            with Path(file_path).open("rb") as f:
                # Read file in chunks to handle large files efficiently
                for chunk in iter(lambda: f.read(8192), b""):
                    hash_func.update(chunk)
            return str(hash_func.hexdigest())
        except OSError as e:
            print(f"Error reading file {file_path}: {e}")
            return ""

    def _get_file_info(
        self, file_path: str, existing_record: tuple | None = None
    ) -> tuple[str, str, str, datetime, int] | None:
        """
        Get file information including path, filename, checksum, and modification time.
        Only calculates checksum if file is new or has been modified.

        Args:
            file_path: Full path to the file
            existing_record: Tuple of (checksum, modification_datetime) from database if exists

        Returns:
            Tuple of (path, filename, checksum, modification_datetime, file_size) or None if error
        """
        try:
            path_obj = Path(file_path)
            stat_info = path_obj.stat()

            directory = str(path_obj.parent)
            filename = path_obj.name
            modification_datetime = datetime.fromtimestamp(stat_info.st_mtime)
            file_size = stat_info.st_size

            # Check if we need to calculate checksum
            if existing_record:
                existing_checksum, existing_mod_time = existing_record
                # If modification time hasn't changed, reuse existing checksum
                if modification_datetime == existing_mod_time:
                    self.checksum_reuses += 1
                    return (
                        directory,
                        filename,
                        existing_checksum,
                        modification_datetime,
                        file_size,
                    )

            # File is new or modified, calculate checksum
            checksum = self._calculate_checksum(file_path)
            if not checksum:  # Skip files we couldn't read
                return None

            self.checksum_calculations += 1
            return (directory, filename, checksum, modification_datetime, file_size)
        except OSError as e:
            print(f"Error accessing file {file_path}: {e}")
            return None

    def scan_directory(self, directory_path: str, recursive: bool = True) -> list[str]:
        """
        Scan directory for all files, ignoring symbolic links.

        Args:
            directory_path: Path to directory to scan
            recursive: Whether to scan subdirectories recursively

        Returns:
            List of file paths (excluding symbolic links)
        """
        files: list[str] = []

        if not Path(directory_path).exists():
            print(f"Directory does not exist: {directory_path}")
            return files

        if not Path(directory_path).is_dir():
            print(f"Path is not a directory: {directory_path}")
            return files

        try:
            if recursive:
                for root, _dirs, filenames in os.walk(directory_path):
                    for filename in filenames:
                        file_path = Path(root) / filename
                        if file_path.is_symlink():
                            self.ignored_symlinks += 1
                            continue
                        files.append(str(file_path))
            else:
                for item in Path(directory_path).iterdir():
                    if item.is_file() and not item.is_symlink():
                        files.append(str(item))
                    elif item.is_symlink():
                        self.ignored_symlinks += 1
        except OSError as e:
            print(f"Error scanning directory {directory_path}: {e}")

        return files

    def update_database(self, directory_path: str, recursive: bool = True) -> None:
        """
        Update database with files from the specified directory.
        Optimized to avoid recalculating checksums for unmodified files.

        Args:
            directory_path: Path to directory to scan
            recursive: Whether to scan subdirectories recursively
        """
        print(f"Scanning directory: {directory_path}")
        # Reset symlink counter for this update operation
        self.ignored_symlinks = 0
        files = self.scan_directory(directory_path, recursive)

        if not files:
            print("No files found to index.")
            return

        print(f"Found {len(files)} files to process...")

        processed = 0
        updated = 0
        added = 0
        errors = 0

        for file_path in files:
            try:
                path_obj = Path(file_path)
                directory = str(path_obj.parent)
                filename = path_obj.name

                # Check if file already exists in database
                existing = self.conn.execute(
                    """
                    SELECT checksum, modification_datetime, file_size
                    FROM files
                    WHERE path = ? AND filename = ?
                """,
                    [directory, filename],
                ).fetchone()

                # Get file info (only calculates checksum if needed)
                file_info = self._get_file_info(
                    file_path, (existing[0], existing[1]) if existing else None
                )

                if not file_info:
                    errors += 1
                    continue

                directory, filename, checksum, modification_datetime, file_size = (
                    file_info
                )

                if existing:
                    existing_checksum, existing_mod_time, existing_size = existing
                    # Check if anything has changed
                    if (
                        checksum != existing_checksum
                        or modification_datetime != existing_mod_time
                        or file_size != existing_size
                    ):
                        # Update record
                        self.conn.execute(
                            """
                            UPDATE files
                            SET checksum = ?, modification_datetime = ?, file_size = ?, indexed_at = CURRENT_TIMESTAMP
                            WHERE path = ? AND filename = ?
                        """,
                            [
                                checksum,
                                modification_datetime,
                                file_size,
                                directory,
                                filename,
                            ],
                        )
                        updated += 1
                    else:
                        # File hasn't changed, no update needed
                        self.skipped_files += 1
                else:
                    # Insert new file
                    self.conn.execute(
                        """
                        INSERT INTO files (path, filename, checksum, modification_datetime, file_size)
                        VALUES (?, ?, ?, ?, ?)
                    """,
                        [
                            directory,
                            filename,
                            checksum,
                            modification_datetime,
                            file_size,
                        ],
                    )
                    added += 1

            except Exception as e:
                print(f"Error processing file {file_path}: {e}")
                errors += 1

            # Increment processed counter for all files (successful or error)
            processed += 1
            if processed % 100 == 0:
                print(f"Processed {processed}/{len(files)} files...")

        print(
            f"Completed! Processed: {processed}, Added: {added}, Updated: {updated}, Skipped: {self.skipped_files}, Errors: {errors}"
        )

        # Show symlinks ignored
        if self.ignored_symlinks > 0:
            print(f"Ignored {self.ignored_symlinks} symbolic links")

        # Show optimization benefits
        total_checksum_ops = self.checksum_calculations + self.checksum_reuses
        if total_checksum_ops > 0:
            optimization_pct = (self.checksum_reuses / total_checksum_ops) * 100
            print(
                f"Performance: Calculated {self.checksum_calculations} checksums, reused {self.checksum_reuses} ({optimization_pct:.1f}% optimization)"
            )
        else:
            print("Performance: No checksum operations performed")

    def search_files(
        self,
        filename_pattern: str | None = None,
        checksum: str | None = None,
        path_pattern: str | None = None,
    ) -> list[dict]:
        """
        Search for files in the database.

        Args:
            filename_pattern: SQL LIKE pattern for filename
            checksum: Exact checksum to match
            path_pattern: SQL LIKE pattern for path

        Returns:
            List of matching file records
        """
        query = "SELECT * FROM files WHERE 1=1"
        params = []

        if filename_pattern:
            query += " AND filename LIKE ?"
            params.append(filename_pattern)

        if checksum:
            query += " AND checksum = ?"
            params.append(checksum)

        if path_pattern:
            query += " AND path LIKE ?"
            params.append(path_pattern)

        query += " ORDER BY path, filename"

        results = self.conn.execute(query, params).fetchall()

        # Convert to list of dictionaries
        columns = [
            "path",
            "filename",
            "checksum",
            "modification_datetime",
            "file_size",
            "indexed_at",
        ]
        return [dict(zip(columns, row, strict=True)) for row in results]

    def find_duplicates(self) -> list[dict]:
        """
        Find files with duplicate checksums.

        Returns:
            List of file records with duplicate checksums
        """
        query = """
        SELECT * FROM files
        WHERE checksum IN (
            SELECT checksum
            FROM files
            GROUP BY checksum
            HAVING COUNT(*) > 1
        )
        ORDER BY checksum, path, filename
        """

        results = self.conn.execute(query).fetchall()
        columns = [
            "path",
            "filename",
            "checksum",
            "modification_datetime",
            "file_size",
            "indexed_at",
        ]
        return [dict(zip(columns, row, strict=True)) for row in results]

    def get_stats(self) -> dict:
        """
        Get database statistics including performance optimization metrics.

        Returns:
            Dictionary with database statistics
        """
        stats = {}

        # Total files
        total_files_result = self.conn.execute("SELECT COUNT(*) FROM files").fetchone()
        stats["total_files"] = total_files_result[0] if total_files_result else 0

        # Total size
        total_size_result = self.conn.execute(
            "SELECT SUM(file_size) FROM files"
        ).fetchone()
        stats["total_size"] = (
            total_size_result[0] if total_size_result and total_size_result[0] else 0
        )

        # Unique checksums
        unique_checksums_result = self.conn.execute(
            "SELECT COUNT(DISTINCT checksum) FROM files"
        ).fetchone()
        stats["unique_checksums"] = (
            unique_checksums_result[0] if unique_checksums_result else 0
        )

        # Duplicate files
        stats["duplicate_files"] = stats["total_files"] - stats["unique_checksums"]

        # Last indexed
        last_indexed_result = self.conn.execute(
            "SELECT MAX(indexed_at) FROM files"
        ).fetchone()
        stats["last_indexed"] = last_indexed_result[0] if last_indexed_result else None

        # Optimization statistics
        stats["checksum_calculations"] = self.checksum_calculations
        stats["checksum_reuses"] = self.checksum_reuses
        stats["skipped_files"] = self.skipped_files
        stats["ignored_symlinks"] = self.ignored_symlinks
        total_operations = self.checksum_calculations + self.checksum_reuses
        if total_operations > 0:
            stats["optimization_percentage"] = round(
                (self.checksum_reuses / total_operations) * 100, 2
            )
        else:
            stats["optimization_percentage"] = 0

        return stats

    def reset_optimization_counters(self) -> None:
        """Reset the optimization performance counters."""
        self.checksum_calculations = 0
        self.checksum_reuses = 0
        self.skipped_files = 0
        self.ignored_symlinks = 0

    def close(self) -> None:
        """Close the database connection."""
        if self.conn:
            self.conn.close()
