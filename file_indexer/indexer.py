"""
Core file indexing functionality using DuckDB with performance optimizations.
"""

import hashlib
import os
from collections.abc import Generator
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb


def _calculate_checksum_worker(
    file_path: str, algorithm: str = "sha256"
) -> tuple[str, str]:
    """
    Worker function for calculating checksums in parallel.
    Returns (file_path, checksum) tuple.
    """
    try:
        path_obj = Path(file_path)

        # Safety check: Skip symlinks and special files
        if path_obj.is_symlink():
            print(f"Skipping symlink during checksum calculation: {file_path}")
            return (file_path, "")

        if not path_obj.is_file():
            print(f"Skipping special file during checksum calculation: {file_path}")
            return (file_path, "")

        hash_func: Any = getattr(hashlib, algorithm)()
        with path_obj.open("rb") as f:
            # Read file in larger chunks for better performance
            for chunk in iter(lambda: f.read(65536), b""):  # 64KB chunks
                hash_func.update(chunk)
        return (file_path, str(hash_func.hexdigest()))
    except PermissionError as e:
        # Permission denied - return empty checksum
        print(f"Permission denied calculating checksum: {file_path} - {e}")
        return (file_path, "")
    except OSError as e:
        # Other OS errors - return empty checksum
        print(f"Error calculating checksum: {file_path} - {e}")
        return (file_path, "")


class FileIndexer:
    def __init__(
        self,
        db_path: str = "file_index.db",
        max_workers: int | None = None,
        max_checksum_size: int = 100 * 1024 * 1024,  # 100MB default
        skip_empty_files: bool = True,
        use_parallel_processing: bool = True,
    ):
        """
        Initialize the FileIndexer with a DuckDB database.

        Args:
            db_path: Path to the DuckDB database file
            max_workers: Maximum number of worker processes for parallel operations
            max_checksum_size: Maximum file size in bytes to calculate checksums for (0 = no limit)
            skip_empty_files: Whether to skip checksum calculation for empty files
            use_parallel_processing: Whether to use parallel processing for checksums (False forces sequential)
        """
        self.db_path = db_path
        self.conn = duckdb.connect(db_path)
        self.max_workers = max_workers or min(32, (os.cpu_count() or 1) + 4)
        self.max_checksum_size = max_checksum_size
        self.skip_empty_files = skip_empty_files
        # Use parallel processing only if explicitly enabled and max_workers > 1
        self.use_parallel_processing = use_parallel_processing and self.max_workers > 1
        self._create_table()
        self._migrate_schema()

        # Statistics for optimization tracking
        self.checksum_calculations = 0
        self.checksum_reuses = 0
        self.skipped_files = 0
        self.ignored_symlinks = 0
        self.ignored_special_files = 0  # Device files, pipes, sockets, etc.
        self.skipped_checksums = 0  # Files that don't get checksums
        self.permission_errors = 0  # Files that couldn't be accessed due to permissions
        self.deleted_files = 0  # Files removed from database during cleanup

    def _create_table(self) -> None:
        """Create the files table if it doesn't exist with nullable checksum."""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS files (
            path VARCHAR NOT NULL,
            filename VARCHAR NOT NULL,
            checksum VARCHAR,  -- Now nullable
            modification_datetime TIMESTAMP NOT NULL,
            file_size BIGINT NOT NULL,
            indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (path, filename)
        );
        """
        self.conn.execute(create_table_sql)

        # Create optimized indexes
        self.conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_checksum ON files(checksum);
        CREATE INDEX IF NOT EXISTS idx_modification_datetime ON files(modification_datetime);
        CREATE INDEX IF NOT EXISTS idx_path_filename ON files(path, filename);
        CREATE INDEX IF NOT EXISTS idx_file_size ON files(file_size);
        """)

    def _migrate_schema(self) -> None:
        """Migrate existing schema to support nullable checksums."""
        try:
            # Check if the checksum column allows NULL
            schema_info = self.conn.execute("PRAGMA table_info(files)").fetchall()
            checksum_column = next(
                (col for col in schema_info if col[1] == "checksum"), None
            )

            if (
                checksum_column and checksum_column[3] == 1
            ):  # NOT NULL constraint exists
                # Need to migrate: create new table, copy data, rename
                print("Migrating database schema to support nullable checksums...")

                self.conn.execute("""
                CREATE TABLE files_new (
                    path VARCHAR NOT NULL,
                    filename VARCHAR NOT NULL,
                    checksum VARCHAR,
                    modification_datetime TIMESTAMP NOT NULL,
                    file_size BIGINT NOT NULL,
                    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (path, filename)
                );
                """)

                # Copy existing data
                self.conn.execute("""
                INSERT INTO files_new
                SELECT path, filename, checksum, modification_datetime, file_size, indexed_at
                FROM files;
                """)

                # Drop old table and rename
                self.conn.execute("DROP TABLE files;")
                self.conn.execute("ALTER TABLE files_new RENAME TO files;")

                # Recreate indexes
                self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_checksum ON files(checksum);
                CREATE INDEX IF NOT EXISTS idx_modification_datetime ON files(modification_datetime);
                CREATE INDEX IF NOT EXISTS idx_path_filename ON files(path, filename);
                CREATE INDEX IF NOT EXISTS idx_file_size ON files(file_size);
                """)

                print("Schema migration completed.")

        except Exception as e:
            print(f"Schema migration failed (this is normal for new databases): {e}")

    def _should_process_file(
        self, file_path: str | Path, check_empty_files: bool = False
    ) -> bool:
        """
        Shared helper function to determine if a file should be processed.
        Handles symlinks, special files, and optionally empty files.
        Updates appropriate counters.

        Args:
            file_path: Path to the file to check
            check_empty_files: Whether to also check for empty files (respects skip_empty_files setting)

        Returns:
            True if the file should be processed, False otherwise
        """
        try:
            path_obj = Path(file_path)

            # Skip symbolic links
            if path_obj.is_symlink():
                self.ignored_symlinks += 1
                return False

            # Skip special files (device files, pipes, sockets, etc.)
            # Only process regular files
            if not path_obj.is_file():
                self.ignored_special_files += 1
                return False

            # Skip empty files if requested and skip_empty_files is True
            if check_empty_files and self.skip_empty_files:
                try:
                    file_size = path_obj.stat().st_size
                    if file_size == 0:
                        self.skipped_checksums += 1
                        return False
                except (OSError, PermissionError):
                    # If we can't get file size, let it through and handle later
                    pass

            return True

        except (OSError, PermissionError):
            # If we can't check the file, assume it's not processable
            return False

    def _should_calculate_checksum(self, file_size: int) -> bool:
        """
        Determine if we should calculate checksum for a file based on size.

        Args:
            file_size: Size of the file in bytes

        Returns:
            True if checksum should be calculated, False otherwise
        """
        # Special case: negative max_checksum_size means skip all checksums
        if self.max_checksum_size < 0:
            return False

        if self.skip_empty_files and file_size == 0:
            return False

        return not (self.max_checksum_size > 0 and file_size > self.max_checksum_size)

    def _calculate_checksum(self, file_path: str, algorithm: str = "sha256") -> str:
        """
        Calculate checksum for a file (kept for compatibility).
        """
        _, checksum = _calculate_checksum_worker(file_path, algorithm)
        return checksum

    def scan_directory_generator(
        self, directory_path: str, recursive: bool = True
    ) -> Generator[str, None, None]:
        """
        Generator that yields file paths one by one, reducing memory usage.

        Args:
            directory_path: Path to directory to scan
            recursive: Whether to scan subdirectories recursively

        Yields:
            File paths (excluding symbolic links, device files, pipes, sockets, etc.)
        """
        if not Path(directory_path).exists():
            print(f"Directory does not exist: {directory_path}")
            return

        if not Path(directory_path).is_dir():
            print(f"Path is not a directory: {directory_path}")
            return

        try:
            if recursive:
                for root, _dirs, filenames in os.walk(directory_path):
                    for filename in filenames:
                        file_path = Path(root) / filename

                        # Use shared helper function
                        if self._should_process_file(file_path):
                            yield str(file_path)
            else:
                for item in Path(directory_path).iterdir():
                    # Use shared helper function
                    if self._should_process_file(item):
                        yield str(item)
        except OSError as e:
            print(f"Error scanning directory {directory_path}: {e}")

    def scan_directory(self, directory_path: str, recursive: bool = True) -> list[str]:
        """
        Scan directory for all files, ignoring symbolic links.
        """
        return list(self.scan_directory_generator(directory_path, recursive))

    def _get_existing_files_bulk(
        self, file_paths: list[str]
    ) -> dict[tuple[str, str], tuple[str | None, datetime, int]]:
        """
        Get existing file records in bulk to avoid N+1 query problem.

        Returns:
            Dictionary mapping (path, filename) to (checksum, modification_datetime, file_size)
        """
        if not file_paths:
            return {}

        # Prepare path-filename pairs
        path_filename_pairs = []
        for file_path in file_paths:
            path_obj = Path(file_path)
            path_filename_pairs.append((str(path_obj.parent), path_obj.name))

        # Build bulk query with IN clause
        placeholders = ",".join(["(?, ?)"] * len(path_filename_pairs))
        query = f"""
        SELECT path, filename, checksum, modification_datetime, file_size
        FROM files
        WHERE (path, filename) IN ({placeholders})
        """

        # Flatten the pairs for the query parameters
        params = []
        for path, filename in path_filename_pairs:
            params.extend([path, filename])

        results = self.conn.execute(query, params).fetchall()

        # Build lookup dictionary
        existing_files = {}
        for path, filename, checksum, mod_time, file_size in results:
            existing_files[(path, filename)] = (checksum, mod_time, file_size)

        return existing_files

    def _process_files_batch(
        self, file_paths: list[str], existing_files: dict
    ) -> tuple[list, list, list]:
        """
        Process a batch of files, determining which need checksum calculation.

        Returns:
            (files_needing_checksums, files_to_update, files_to_insert)
        """
        files_needing_checksums = []
        files_to_update = []
        files_to_insert = []

        for file_path in file_paths:
            try:
                path_obj = Path(file_path)
                stat_info = path_obj.stat()

                directory = str(path_obj.parent)
                filename = path_obj.name
                modification_datetime = datetime.fromtimestamp(stat_info.st_mtime)
                file_size = stat_info.st_size

                existing_record = existing_files.get((directory, filename))
                should_calc_checksum = self._should_calculate_checksum(file_size)

                if existing_record:
                    existing_checksum, existing_mod_time, existing_size = (
                        existing_record
                    )
                    # Check if file has been modified
                    if (
                        modification_datetime == existing_mod_time
                        and file_size == existing_size
                    ):
                        # File unchanged, skip
                        if (
                            existing_checksum is not None
                        ):  # Only count as reuse if there was actually a checksum
                            self.checksum_reuses += 1
                        self.skipped_files += 1
                        continue
                    else:
                        # File modified, needs processing
                        if should_calc_checksum:
                            files_needing_checksums.append(file_path)
                        else:
                            self.skipped_checksums += 1
                        files_to_update.append(
                            (
                                file_path,
                                directory,
                                filename,
                                modification_datetime,
                                file_size,
                                should_calc_checksum,
                            )
                        )
                else:
                    # New file, needs processing
                    if should_calc_checksum:
                        files_needing_checksums.append(file_path)
                    else:
                        self.skipped_checksums += 1
                    files_to_insert.append(
                        (
                            file_path,
                            directory,
                            filename,
                            modification_datetime,
                            file_size,
                            should_calc_checksum,
                        )
                    )

            except PermissionError:
                # Skip files we can't access due to permissions
                print(f"Permission denied: {file_path}")
                self.permission_errors += 1
                continue
            except OSError as e:
                # For other OS errors, show the message but continue
                print(f"Error accessing file {file_path}: {e}")
                continue

        return files_needing_checksums, files_to_update, files_to_insert

    def _calculate_checksums_parallel(self, file_paths: list[str]) -> dict[str, str]:
        """Calculate checksums for multiple files in parallel, with fallback to sequential processing."""
        if not file_paths:
            return {}

        # Use sequential processing if parallel processing is disabled or max_workers is 1
        if not self.use_parallel_processing:
            return self._calculate_checksums_sequential(file_paths)

        checksums = {}

        # Try parallel processing first
        try:
            with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit all checksum calculations
                future_to_path = {
                    executor.submit(_calculate_checksum_worker, file_path): file_path
                    for file_path in file_paths
                }

                # Collect results as they complete
                for future in as_completed(future_to_path):
                    try:
                        file_path, checksum = future.result()
                        if checksum:  # Only store successful checksums
                            checksums[file_path] = checksum
                            self.checksum_calculations += 1
                        # Note: Permission errors are already reported by the worker process
                    except Exception as e:
                        file_path = future_to_path[future]
                        print(f"Error calculating checksum for {file_path}: {e}")

        except (PermissionError, OSError) as e:
            # Fall back to sequential processing when parallel processing is not available
            print(
                f"Parallel processing not available ({e}), falling back to sequential processing..."
            )
            checksums = self._calculate_checksums_sequential(file_paths)

        return checksums

    def _calculate_checksums_sequential(self, file_paths: list[str]) -> dict[str, str]:
        """Calculate checksums for multiple files sequentially (fallback method)."""
        checksums = {}

        for file_path in file_paths:
            try:
                _, checksum = _calculate_checksum_worker(file_path)
                if checksum:  # Only store successful checksums
                    checksums[file_path] = checksum
                    self.checksum_calculations += 1
            except Exception as e:
                print(f"Error calculating checksum for {file_path}: {e}")

        return checksums

    def _bulk_database_operations(
        self, inserts: list, updates: list
    ) -> tuple[int, int]:
        """Perform bulk database operations."""
        added = 0
        updated = 0

        # Begin transaction for better performance
        self.conn.execute("BEGIN TRANSACTION")

        try:
            # Bulk inserts
            if inserts:
                insert_sql = """
                INSERT INTO files (path, filename, checksum, modification_datetime, file_size)
                VALUES (?, ?, ?, ?, ?)
                """
                self.conn.executemany(insert_sql, inserts)
                added = len(inserts)

            # Bulk updates
            if updates:
                update_sql = """
                UPDATE files
                SET checksum = ?, modification_datetime = ?, file_size = ?, indexed_at = CURRENT_TIMESTAMP
                WHERE path = ? AND filename = ?
                """
                self.conn.executemany(update_sql, updates)
                updated = len(updates)

            self.conn.execute("COMMIT")

        except Exception as e:
            self.conn.execute("ROLLBACK")
            print(f"Database operation failed: {e}")
            raise

        return added, updated

    def update_database(
        self, directory_path: str, recursive: bool = True, batch_size: int = 1000
    ) -> None:
        """
        Update database with files from the specified directory using optimized batch processing.

        Args:
            directory_path: Path to directory to scan
            recursive: Whether to scan subdirectories recursively
            batch_size: Number of files to process in each batch
        """
        print(f"Scanning directory: {directory_path}")
        print(
            f"Configuration: max_checksum_size={self.max_checksum_size:,} bytes, skip_empty_files={self.skip_empty_files}"
        )

        # Reset only per-scan counters (not cumulative performance counters)
        self.ignored_symlinks = 0
        self.ignored_special_files = 0
        self.skipped_checksums = 0
        self.skipped_files = 0
        self.permission_errors = 0

        # Process files in batches to manage memory usage
        file_generator = self.scan_directory_generator(directory_path, recursive)

        total_processed = 0
        total_added = 0
        total_updated = 0
        total_errors = 0

        # Process files in batches
        batch = []
        for file_path in file_generator:
            batch.append(file_path)

            if len(batch) >= batch_size:
                added, updated, errors = self._process_batch(batch)
                total_processed += len(batch)
                total_added += added
                total_updated += updated
                total_errors += errors

                print(f"Processed {total_processed} files...")
                batch = []

        # Process remaining files in the last batch
        if batch:
            added, updated, errors = self._process_batch(batch)
            total_processed += len(batch)
            total_added += added
            total_updated += updated
            total_errors += errors

        print(
            f"Completed! Processed: {total_processed}, Added: {total_added}, Updated: {total_updated}, Skipped: {self.skipped_files}, Errors: {total_errors}"
        )

        if self.ignored_symlinks > 0:
            print(f"Ignored {self.ignored_symlinks} symbolic links")
        if self.ignored_special_files > 0:
            print(
                f"Ignored {self.ignored_special_files} special files (device files, pipes, sockets, etc.)"
            )

        if self.skipped_checksums > 0:
            print(
                f"Skipped checksums for {self.skipped_checksums} files (empty or too large)"
            )

        if self.permission_errors > 0:
            print(f"Permission denied for {self.permission_errors} files")

        # Show optimization benefits
        total_checksum_ops = self.checksum_calculations + self.checksum_reuses
        if total_checksum_ops > 0:
            optimization_pct = (self.checksum_reuses / total_checksum_ops) * 100
            print(
                f"Performance: Calculated {self.checksum_calculations} checksums, reused {self.checksum_reuses} ({optimization_pct:.1f}% optimization)"
            )

    def _process_batch(self, file_paths: list[str]) -> tuple[int, int, int]:
        """Process a batch of files with improved error handling."""
        try:
            # Get existing file records in bulk
            existing_files = self._get_existing_files_bulk(file_paths)

            # Determine which files need processing (with individual file error handling)
            files_needing_checksums, files_to_update, files_to_insert = (
                self._process_files_batch(file_paths, existing_files)
            )

            # Calculate checksums in parallel
            checksums = self._calculate_checksums_parallel(files_needing_checksums)

            # Prepare database operations
            insert_data = []
            update_data = []

            for (
                file_path,
                directory,
                filename,
                mod_time,
                file_size,
                needs_checksum,
            ) in files_to_insert:
                if needs_checksum:
                    checksum = checksums.get(file_path)
                    if checksum is None and file_path in files_needing_checksums:
                        continue  # Skip files where checksum calculation failed
                else:
                    checksum = None  # Explicitly set to NULL for large/empty files

                insert_data.append(
                    (directory, filename, checksum, mod_time.isoformat(), file_size)
                )

            for (
                file_path,
                directory,
                filename,
                mod_time,
                file_size,
                needs_checksum,
            ) in files_to_update:
                if needs_checksum:
                    checksum = checksums.get(file_path)
                    if checksum is None and file_path in files_needing_checksums:
                        continue  # Skip files where checksum calculation failed
                else:
                    checksum = None  # Explicitly set to NULL for large/empty files

                update_data.append(
                    (checksum, mod_time.isoformat(), file_size, directory, filename)
                )

            # Perform bulk database operations
            added, updated = self._bulk_database_operations(insert_data, update_data)

            errors = len(files_needing_checksums) - len(checksums)
            return added, updated, errors

        except PermissionError as e:
            print(f"Permission denied accessing files in batch: {e}")
            # Try to process files individually to save what we can
            return self._process_batch_individually(file_paths)
        except Exception as e:
            print(f"Error processing batch: {e}")
            # Try to process files individually to save what we can
            return self._process_batch_individually(file_paths)

    def _process_batch_individually(
        self, file_paths: list[str]
    ) -> tuple[int, int, int]:
        """Process files individually when batch processing fails."""
        added = 0
        updated = 0
        errors = 0

        for file_path in file_paths:
            try:
                # Process single file using the legacy method for reliability
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
                                modification_datetime.isoformat(),
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
                            modification_datetime.isoformat(),
                            file_size,
                        ],
                    )
                    added += 1

            except PermissionError:
                # Skip files we can't access due to permissions
                print(f"Permission denied: {file_path}")
                self.permission_errors += 1
                errors += 1
                continue
            except Exception as e:
                print(f"Error processing file {file_path}: {e}")
                errors += 1
                continue

        return added, updated, errors

    def search_files(
        self,
        filename_pattern: str | None = None,
        checksum: str | None = None,
        path_pattern: str | None = None,
        has_checksum: bool | None = None,
    ) -> list[dict]:
        """
        Search for files in the database.

        Args:
            filename_pattern: SQL LIKE pattern for filename
            checksum: Exact checksum to match
            path_pattern: SQL LIKE pattern for path
            has_checksum: Filter by whether files have checksums (True/False/None for all)

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

        if has_checksum is not None:
            if has_checksum:
                query += " AND checksum IS NOT NULL"
            else:
                query += " AND checksum IS NULL"

        query += " ORDER BY path, filename"

        results = self.conn.execute(query, params).fetchall()

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
        Find files with duplicate checksums (excluding files without checksums).

        Returns:
            List of file records with duplicate checksums
        """
        query = """
        SELECT * FROM files
        WHERE checksum IS NOT NULL
        AND checksum IN (
            SELECT checksum
            FROM files
            WHERE checksum IS NOT NULL
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
        """Get database statistics including performance optimization metrics."""
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

        # Files with checksums
        files_with_checksum_result = self.conn.execute(
            "SELECT COUNT(*) FROM files WHERE checksum IS NOT NULL"
        ).fetchone()
        stats["files_with_checksum"] = (
            files_with_checksum_result[0] if files_with_checksum_result else 0
        )

        # Files without checksums
        stats["files_without_checksum"] = (
            stats["total_files"] - stats["files_with_checksum"]
        )

        # Unique checksums (only count non-null checksums)
        unique_checksums_result = self.conn.execute(
            "SELECT COUNT(DISTINCT checksum) FROM files WHERE checksum IS NOT NULL"
        ).fetchone()
        stats["unique_checksums"] = (
            unique_checksums_result[0] if unique_checksums_result else 0
        )

        # Duplicate files (only among files with checksums)
        stats["duplicate_files"] = (
            stats["files_with_checksum"] - stats["unique_checksums"]
        )

        # Last indexed
        last_indexed_result = self.conn.execute(
            "SELECT MAX(indexed_at) FROM files"
        ).fetchone()
        stats["last_indexed"] = last_indexed_result[0] if last_indexed_result else None

        # Performance statistics
        stats["checksum_calculations"] = self.checksum_calculations
        stats["checksum_reuses"] = self.checksum_reuses
        stats["skipped_files"] = self.skipped_files
        stats["ignored_symlinks"] = self.ignored_symlinks
        stats["ignored_special_files"] = self.ignored_special_files
        stats["skipped_checksums"] = self.skipped_checksums
        stats["permission_errors"] = self.permission_errors
        stats["deleted_files"] = self.deleted_files

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
        self.ignored_special_files = 0
        self.skipped_checksums = 0
        self.permission_errors = 0
        self.deleted_files = 0

    def _check_directory_existence(
        self, directory_path: str
    ) -> tuple[bool, str | None]:
        """
        Check if a directory exists.

        Args:
            directory_path: Path to the directory to check

        Returns:
            Tuple of (exists: bool, error_message: str | None)
            - (True, None): Directory exists
            - (False, None): Directory doesn't exist
            - (False, error_message): Error occurred during check
        """
        try:
            path_obj = Path(directory_path)
            return (path_obj.exists(), None)
        except PermissionError:
            return (False, f"Permission denied checking directory: {directory_path}")
        except OSError as e:
            return (False, f"Error checking directory {directory_path}: {e}")

    def _mark_directory_files_as_deleted(
        self,
        directory_path: str,
        files_in_dir: list[tuple[str, int, str]],
        deleted_files: list[tuple[str, str]],
        deleted_directories: set[str],
    ) -> int:
        """
        Mark all files in a deleted directory as deleted.

        Args:
            directory_path: Path of the deleted directory
            files_in_dir: List of (filename, file_size, indexed_at) tuples
            deleted_files: List to append deleted file records to
            deleted_directories: Set to add the deleted directory to

        Returns:
            Number of files marked as deleted
        """
        deleted_directories.add(directory_path)
        files_marked = 0

        for filename, _file_size, _indexed_at in files_in_dir:
            deleted_files.append((directory_path, filename))
            files_marked += 1

        return files_marked

    def _handle_directory_access_error(
        self,
        directory_path: str,
        files_in_dir: list[tuple[str, int, str]],
        error_message: str,
        directories_to_process_individually: dict[str, list[tuple[str, int, str]]],
        deleted_files: list[tuple[str, str]],
        deleted_directories: set[str],
    ) -> tuple[int, int]:
        """
        Handle errors when accessing directories during cleanup.

        Args:
            directory_path: Path of the directory with access issues
            files_in_dir: List of files in the directory
            error_message: Error message to log
            directories_to_process_individually: Dict to add directories that need individual file checks
            deleted_files: List to append deleted file records to (for OS errors)
            deleted_directories: Set to add deleted directories to (for OS errors)

        Returns:
            Tuple of (permission_errors_count, files_marked_as_deleted)
        """
        print(error_message)

        if "Permission denied" in error_message:
            # For permission errors, still try to check individual files
            directories_to_process_individually[directory_path] = files_in_dir
            return (1, 0)
        else:
            # For other OS errors, treat as deleted directory
            files_marked = self._mark_directory_files_as_deleted(
                directory_path, files_in_dir, deleted_files, deleted_directories
            )
            return (0, files_marked)

    def _report_phase1_progress(
        self, checked_directories: int, total_directories: int
    ) -> None:
        """
        Report progress during Phase 1 directory checking.

        Args:
            checked_directories: Number of directories checked so far
            total_directories: Total number of directories to check
        """
        if checked_directories % 100 == 0:
            print(
                f"  Checked {checked_directories:,}/{total_directories:,} directories..."
            )

    def _delete_files_from_deleted_directories(
        self,
        deleted_directories: set[str],
        files_by_directory: dict[str, list[tuple[str, int, str]]],
        batch_size: int,
    ) -> None:
        """
        Delete database records for all files in directories that were entirely deleted.

        Args:
            deleted_directories: Set of directory paths that no longer exist
            files_by_directory: Dict mapping directory paths to their file lists
            batch_size: Number of files to delete in each batch
        """
        if not deleted_directories:
            return

        directory_files_to_delete = []
        for directory_path in deleted_directories:
            for filename, _, _ in files_by_directory[directory_path]:
                directory_files_to_delete.append((directory_path, filename))

        if directory_files_to_delete:
            # Process in batches to avoid overwhelming the database
            for i in range(0, len(directory_files_to_delete), batch_size):
                batch = directory_files_to_delete[i : i + batch_size]
                self._delete_files_from_database(batch)

    def cleanup_deleted_files(
        self, batch_size: int = 1000, dry_run: bool = False
    ) -> dict:
        """
        Check for deleted files and directories, and clean up the database.
        Optimized to check directories first to reduce filesystem calls.

        Args:
            batch_size: Number of files to check in each batch
            dry_run: If True, only report what would be deleted without actually deleting

        Returns:
            Dictionary with cleanup statistics
        """
        print("Starting database cleanup for deleted files...")
        if dry_run:
            print("DRY RUN MODE: No files will be deleted from database")

        # Reset deleted files counter
        self.deleted_files = 0

        # Get all files from database grouped by directory
        print("Retrieving all files from database...")
        all_files_query = """
        SELECT path, filename, file_size, indexed_at
        FROM files
        ORDER BY path, filename
        """

        all_files = self.conn.execute(all_files_query).fetchall()
        total_db_files = len(all_files)
        print(f"Found {total_db_files:,} files in database")

        if total_db_files == 0:
            print("No files in database to check")
            return {
                "total_checked": 0,
                "deleted_files": 0,
                "deleted_directories": 0,
                "permission_errors": 0,
                "dry_run": dry_run,
            }

        # Group files by directory for efficient checking
        print("Grouping files by directory for optimization...")
        files_by_directory: dict[str, list[tuple[str, int, str]]] = {}
        for path, filename, file_size, indexed_at in all_files:
            if path not in files_by_directory:
                files_by_directory[path] = []
            files_by_directory[path].append((filename, file_size, indexed_at))

        print(f"Found {len(files_by_directory):,} unique directories")

        # Track statistics
        deleted_files: list[tuple[str, str]] = []
        deleted_directories: set[str] = set()
        permission_errors = 0
        checked_files = 0
        checked_directories = 0
        files_deleted_by_directory = (
            0  # Files deleted because their directory was deleted
        )
        files_deleted_individually = 0  # Files deleted after individual checks

        # Phase 1: Check directories first
        print("Phase 1: Checking directories...")
        directories_to_process_individually: dict[str, list[tuple[str, int, str]]] = {}

        for directory_path, files_in_dir in files_by_directory.items():
            checked_directories += 1

            # Check if directory exists
            exists, error_message = self._check_directory_existence(directory_path)

            if error_message:
                # Handle access errors (permission denied, OS errors)
                perm_errors, files_marked = self._handle_directory_access_error(
                    directory_path,
                    files_in_dir,
                    error_message,
                    directories_to_process_individually,
                    deleted_files,
                    deleted_directories,
                )
                permission_errors += perm_errors
                files_deleted_by_directory += files_marked
                checked_files += files_marked
            elif not exists:
                # Directory doesn't exist - mark all files as deleted
                files_marked = self._mark_directory_files_as_deleted(
                    directory_path, files_in_dir, deleted_files, deleted_directories
                )
                files_deleted_by_directory += files_marked
                checked_files += files_marked
            else:
                # Directory exists - need to check individual files
                directories_to_process_individually[directory_path] = files_in_dir

            # Progress reporting
            self._report_phase1_progress(checked_directories, len(files_by_directory))

        print(
            f"Phase 1 completed: {len(deleted_directories):,} directories deleted entirely"
        )
        print(
            f"  Files marked as deleted due to directory deletion: {files_deleted_by_directory:,}"
        )
        print(
            f"  Directories needing individual file checks: {len(directories_to_process_individually):,}"
        )

        # Phase 2: Check individual files in remaining directories
        if directories_to_process_individually:
            print("Phase 2: Checking individual files in existing directories...")

            # Process remaining files in batches
            remaining_files = []
            for (
                directory_path,
                files_in_dir,
            ) in directories_to_process_individually.items():
                for filename, file_size, indexed_at in files_in_dir:
                    remaining_files.append(
                        (directory_path, filename, file_size, indexed_at)
                    )

            for i in range(0, len(remaining_files), batch_size):
                batch = remaining_files[i : i + batch_size]
                batch_deleted = []

                for path, filename, _file_size, _indexed_at in batch:
                    checked_files += 1
                    full_path = Path(path) / filename

                    try:
                        # Check if individual file exists
                        if not full_path.exists():
                            deleted_files.append((path, filename))
                            batch_deleted.append((path, filename))
                            files_deleted_individually += 1

                        # Progress reporting
                        if checked_files % 5000 == 0:
                            print(
                                f"  Checked {checked_files:,}/{total_db_files:,} files..."
                            )

                    except PermissionError:
                        permission_errors += 1
                        print(f"Permission denied checking: {full_path}")
                    except OSError as e:
                        # Other filesystem errors - treat as missing file
                        print(f"Error checking file {full_path}: {e}")
                        deleted_files.append((path, filename))
                        batch_deleted.append((path, filename))
                        files_deleted_individually += 1

                # Delete this batch from database if not dry run
                if batch_deleted and not dry_run:
                    self._delete_files_from_database(batch_deleted)

            print(
                f"Phase 2 completed: {files_deleted_individually:,} individual files deleted"
            )

        # Delete files from directories that were entirely deleted (if not already done in batches)
        if deleted_directories and not dry_run:
            self._delete_files_from_deleted_directories(
                deleted_directories, files_by_directory, batch_size
            )

        # Report results
        print("\nCleanup scan completed:")
        print(f"  Directories checked: {checked_directories:,}")
        print(f"  Files checked: {checked_files:,}")
        print(f"  Files found to be deleted: {len(deleted_files):,}")
        print(
            f"    - Deleted due to directory deletion: {files_deleted_by_directory:,}"
        )
        print(f"    - Deleted individually: {files_deleted_individually:,}")
        print(f"  Directories no longer existing: {len(deleted_directories):,}")

        if permission_errors > 0:
            print(f"  Permission errors: {permission_errors:,}")

        # Performance benefit reporting
        # Without optimization, we would check every file individually
        # With optimization, we check directories first and skip individual file checks for deleted directories
        total_potential_checks = total_db_files  # Would check each file individually
        saved_checks = (
            files_deleted_by_directory  # Files we didn't need to check individually
        )
        if saved_checks > 0:
            savings_pct = (saved_checks / total_potential_checks) * 100
            print(
                f"  Optimization: Saved {saved_checks:,} filesystem calls ({savings_pct:.1f}% reduction)"
            )

        if deleted_files:
            print("\nSample of deleted files:")
            for path, filename in deleted_files[:10]:  # Show first 10
                print(f"  {Path(path) / filename}")
            if len(deleted_files) > 10:
                print(f"  ... and {len(deleted_files) - 10:,} more")

        if deleted_directories:
            print("\nDirectories no longer existing:")
            for directory in sorted(deleted_directories):
                print(f"  {directory}")

        # Update counter
        self.deleted_files = len(deleted_files)

        if not dry_run and deleted_files:
            print(
                f"\nDatabase cleanup completed: {len(deleted_files):,} records removed"
            )
        elif dry_run and deleted_files:
            print(
                f"\nDRY RUN: Would remove {len(deleted_files):,} records from database"
            )
        else:
            print("\nNo cleanup needed - all database files still exist")

        return {
            "total_checked": checked_files,
            "deleted_files": len(deleted_files),
            "deleted_directories": len(deleted_directories),
            "permission_errors": permission_errors,
            "files_deleted_by_directory": files_deleted_by_directory,
            "files_deleted_individually": files_deleted_individually,
            "filesystem_calls_saved": saved_checks if saved_checks > 0 else 0,
            "dry_run": dry_run,
        }

    def _delete_files_from_database(self, file_records: list[tuple[str, str]]) -> None:
        """
        Delete multiple file records from the database in bulk.

        Args:
            file_records: List of (path, filename) tuples to delete
        """
        if not file_records:
            return

        self.conn.execute("BEGIN TRANSACTION")

        try:
            delete_sql = """
            DELETE FROM files
            WHERE path = ? AND filename = ?
            """
            self.conn.executemany(delete_sql, file_records)
            self.conn.execute("COMMIT")

        except Exception as e:
            self.conn.execute("ROLLBACK")
            print(f"Database deletion failed: {e}")
            raise

    def cleanup_empty_directories(self, dry_run: bool = False) -> dict:
        """
        Find and optionally remove database records for directories that no longer contain any files.

        Args:
            dry_run: If True, only report what would be cleaned without actually cleaning

        Returns:
            Dictionary with cleanup statistics
        """
        print("Checking for empty directories in database...")
        if dry_run:
            print("DRY RUN MODE: No records will be deleted")

        # Get all unique directories from database
        directories_query = """
        SELECT DISTINCT path, COUNT(*) as file_count
        FROM files
        GROUP BY path
        ORDER BY path
        """

        directories = self.conn.execute(directories_query).fetchall()
        total_directories = len(directories)
        print(f"Found {total_directories:,} directories in database")

        if total_directories == 0:
            return {
                "total_checked": 0,
                "empty_directories": 0,
                "files_in_empty_dirs": 0,
                "permission_errors": 0,
                "dry_run": dry_run,
            }

        empty_directories = []
        permission_errors = 0
        files_in_empty_dirs = 0
        checked_directories = 0

        for directory_path, file_count in directories:
            checked_directories += 1

            try:
                path_obj = Path(directory_path)

                # Check if directory exists
                if not path_obj.exists():
                    empty_directories.append(directory_path)
                    files_in_empty_dirs += file_count
                    continue

                # Check if directory is actually empty
                if path_obj.is_dir():
                    try:
                        # Check if directory has any files (not just what's in our database)
                        has_files = any(path_obj.iterdir())
                        if not has_files:
                            empty_directories.append(directory_path)
                            files_in_empty_dirs += file_count
                    except PermissionError:
                        permission_errors += 1
                        print(f"Permission denied checking directory: {directory_path}")

                # Progress reporting
                if checked_directories % 100 == 0:
                    print(
                        f"Checked {checked_directories:,}/{total_directories:,} directories..."
                    )

            except PermissionError:
                permission_errors += 1
                print(f"Permission denied checking: {directory_path}")
            except OSError as e:
                print(f"Error checking directory {directory_path}: {e}")
                empty_directories.append(directory_path)
                files_in_empty_dirs += file_count

        # Remove records for empty directories if not dry run
        if empty_directories and not dry_run:
            self._delete_directories_from_database(empty_directories)

        # Report results
        print("\nEmpty directory scan completed:")
        print(f"  Directories checked: {checked_directories:,}")
        print(f"  Empty directories found: {len(empty_directories):,}")
        print(f"  Files in empty directories: {files_in_empty_dirs:,}")

        if permission_errors > 0:
            print(f"  Permission errors: {permission_errors:,}")

        if empty_directories:
            print("\nEmpty directories:")
            for directory in empty_directories[:20]:  # Show first 20
                print(f"  {directory}")
            if len(empty_directories) > 20:
                print(f"  ... and {len(empty_directories) - 20:,} more")

        if not dry_run and empty_directories:
            print(
                f"\nCleaned up {files_in_empty_dirs:,} records from {len(empty_directories):,} empty directories"
            )
        elif dry_run and empty_directories:
            print(
                f"\nDRY RUN: Would remove {files_in_empty_dirs:,} records from {len(empty_directories):,} empty directories"
            )
        else:
            print("\nNo empty directories found")

        return {
            "total_checked": checked_directories,
            "empty_directories": len(empty_directories),
            "files_in_empty_dirs": files_in_empty_dirs,
            "permission_errors": permission_errors,
            "dry_run": dry_run,
        }

    def _delete_directories_from_database(self, directories: list[str]) -> None:
        """
        Delete all file records for the specified directories from the database.

        Args:
            directories: List of directory paths to delete records for
        """
        if not directories:
            return

        self.conn.execute("BEGIN TRANSACTION")

        try:
            # Use IN clause for efficient deletion
            placeholders = ",".join(["?"] * len(directories))
            delete_sql = f"""
            DELETE FROM files
            WHERE path IN ({placeholders})
            """
            self.conn.execute(delete_sql, directories)
            self.conn.execute("COMMIT")

        except Exception as e:
            self.conn.execute("ROLLBACK")
            print(f"Database directory deletion failed: {e}")
            raise

    def close(self) -> None:
        """Close the database connection."""
        if self.conn:
            self.conn.close()

    def index_files_without_checksums(
        self, directory_path: str, recursive: bool = True, batch_size: int = 1000
    ) -> None:
        """
        Phase 1: Index all files without calculating checksums.
        This is much faster as it only collects file metadata.

        Args:
            directory_path: Path to directory to scan
            recursive: Whether to scan subdirectories recursively
            batch_size: Number of files to process in each batch
        """
        print(f"Phase 1: Indexing files without checksums from: {directory_path}")

        # Temporarily disable checksum calculation for all files
        original_max_checksum_size = self.max_checksum_size
        self.max_checksum_size = -1  # Negative value means skip all checksums

        try:
            self.update_database(directory_path, recursive, batch_size)
        finally:
            # Restore original setting
            self.max_checksum_size = original_max_checksum_size

        print("Phase 1 completed: All files indexed without checksums")

    def calculate_checksums_for_duplicates(self, batch_size: int = 500) -> None:
        """
        Phase 2: Calculate checksums only for files that have the same size as other files.
        This identifies potential duplicates efficiently.
        Respects the skip_empty_files setting.

        Args:
            batch_size: Number of files to process checksums for in each batch
        """
        print("Phase 2: Finding files with duplicate sizes...")

        # Find all file sizes that have multiple files
        # Exclude empty files if skip_empty_files is True
        if self.skip_empty_files:
            duplicate_sizes_query = """
            SELECT file_size, COUNT(*) as file_count
            FROM files
            WHERE checksum IS NULL AND file_size > 0
            GROUP BY file_size
            HAVING COUNT(*) > 1
            ORDER BY file_size
            """
            print("Skipping empty files in duplicate detection (skip_empty_files=True)")
        else:
            duplicate_sizes_query = """
            SELECT file_size, COUNT(*) as file_count
            FROM files
            WHERE checksum IS NULL
            GROUP BY file_size
            HAVING COUNT(*) > 1
            ORDER BY file_size
            """

        duplicate_sizes = self.conn.execute(duplicate_sizes_query).fetchall()

        if not duplicate_sizes:
            print("No files with duplicate sizes found. No checksums needed.")
            return

        total_duplicate_files = sum(count for _, count in duplicate_sizes)
        print(f"Found {len(duplicate_sizes)} different file sizes with duplicates")
        print(f"Total files that need checksum calculation: {total_duplicate_files}")

        # Process files by size groups
        total_processed = 0
        total_updated = 0

        for file_size, file_count in duplicate_sizes:
            print(f"Processing {file_count} files of size {file_size:,} bytes...")

            # Get all files with this size that don't have checksums
            # Apply the same empty file filtering as in the duplicate size query
            if self.skip_empty_files and file_size == 0:
                # Skip empty files - this shouldn't happen due to the outer query filter,
                # but adding this as a safety check
                continue

            files_query = """
            SELECT path, filename
            FROM files
            WHERE file_size = ? AND checksum IS NULL
            ORDER BY path, filename
            """

            files_with_size = self.conn.execute(files_query, [file_size]).fetchall()
            file_paths = [
                str(Path(path) / filename) for path, filename in files_with_size
            ]

            # Process in batches
            for i in range(0, len(file_paths), batch_size):
                batch_paths = file_paths[i : i + batch_size]
                updated_count = self._calculate_checksums_for_files(batch_paths)
                total_updated += updated_count
                total_processed += len(batch_paths)

                print(
                    f"  Processed {min(i + batch_size, len(file_paths))}/{len(file_paths)} files for this size"
                )

        print(
            f"Phase 2 completed: Processed {total_processed} files, updated {total_updated} with checksums"
        )

        # Move all summary reporting to the end for better organization
        if self.ignored_symlinks > 0:
            print(
                f"Ignored {self.ignored_symlinks} symbolic links during checksum calculation"
            )
        if self.ignored_special_files > 0:
            print(
                f"Ignored {self.ignored_special_files} special files during checksum calculation"
            )
        if self.skipped_checksums > 0:
            print(
                f"Skipped checksums for {self.skipped_checksums} files (empty or too large)"
            )

        # Show final statistics
        stats = self.get_stats()
        print(
            f"Final stats: {stats['files_with_checksum']} files with checksums, "
            f"{stats['files_without_checksum']} without checksums"
        )

    def _calculate_checksums_for_files(self, file_paths: list[str]) -> int:
        """
        Calculate checksums for a specific list of files and update the database.
        Filters out symlinks and special files during processing.

        Args:
            file_paths: List of file paths to calculate checksums for

        Returns:
            Number of files successfully updated with checksums
        """
        if not file_paths:
            return 0

        # Filter out symlinks, special files, and empty files before checksum calculation
        valid_file_paths = []
        for file_path in file_paths:
            # Use shared helper function with empty file checking
            if self._should_process_file(file_path, check_empty_files=True):
                valid_file_paths.append(file_path)

        if not valid_file_paths:
            return 0

        # Calculate checksums in parallel for valid files only
        checksums = self._calculate_checksums_parallel(valid_file_paths)

        if not checksums:
            return 0

        # Prepare database updates
        update_data = []
        for file_path in valid_file_paths:
            if file_path in checksums:
                path_obj = Path(file_path)
                directory = str(path_obj.parent)
                filename = path_obj.name
                checksum = checksums[file_path]

                # Update record with checksum (keep existing modification_datetime and file_size)
                update_data.append((checksum, directory, filename))

        if not update_data:
            return 0

        # Perform bulk database update
        self.conn.execute("BEGIN TRANSACTION")

        try:
            update_sql = """
            UPDATE files
            SET checksum = ?, indexed_at = CURRENT_TIMESTAMP
            WHERE path = ? AND filename = ?
            """
            self.conn.executemany(update_sql, update_data)
            self.conn.execute("COMMIT")

            return len(update_data)

        except Exception as e:
            self.conn.execute("ROLLBACK")
            print(f"Database update failed: {e}")
            return 0

    def two_phase_indexing(
        self, directory_path: str, recursive: bool = True, batch_size: int = 1000
    ) -> None:
        """
        Perform complete two-phase indexing:
        Phase 1: Index all files without checksums (fast)
        Phase 2: Calculate checksums only for files with duplicate sizes (targeted)

        Args:
            directory_path: Path to directory to scan
            recursive: Whether to scan subdirectories recursively
            batch_size: Number of files to process in each batch
        """
        print("Starting two-phase indexing process...")
        print("=" * 50)

        # Reset counters
        self.reset_optimization_counters()

        # Phase 1: Index without checksums
        self.index_files_without_checksums(directory_path, recursive, batch_size)

        print("\n" + "=" * 50)

        # Phase 2: Calculate checksums for potential duplicates
        self.calculate_checksums_for_duplicates(
            batch_size // 2
        )  # Smaller batch for checksum calculation

        print("\n" + "=" * 50)
        print("Two-phase indexing completed!")

        # Show final performance statistics
        stats = self.get_stats()
        print("\nFinal Statistics:")
        print(f"  Total files: {stats['total_files']:,}")
        print(f"  Files with checksums: {stats['files_with_checksum']:,}")
        print(f"  Files without checksums: {stats['files_without_checksum']:,}")
        print(f"  Potential duplicates found: {stats['duplicate_files']:,}")
        print(f"  Total size: {stats['total_size']:,} bytes")

        if stats["checksum_calculations"] > 0:
            print(f"  Checksum calculations: {stats['checksum_calculations']:,}")
            print(
                f"  Optimization: {stats['optimization_percentage']:.1f}% checksums avoided"
            )

    # Compatibility methods to maintain the same interface
    def _get_file_info(
        self, file_path: str, existing_record: tuple | None = None
    ) -> tuple[str, str, str | None, datetime, int] | None:
        """
        Get file information including path, filename, checksum, and modification time.
        Maintains compatibility with the old interface but supports nullable checksums.
        Filters out symlinks and special files.
        """
        try:
            # Use shared helper function
            if not self._should_process_file(file_path):
                return None

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
                    if (
                        existing_checksum is not None
                    ):  # Only count as reuse if there was actually a checksum
                        self.checksum_reuses += 1
                    return (
                        directory,
                        filename,
                        existing_checksum,
                        modification_datetime,
                        file_size,
                    )

            # File is new or modified
            if self._should_calculate_checksum(file_size):
                checksum = self._calculate_checksum(file_path)
                if not checksum:  # Skip files we couldn't read
                    return None
                self.checksum_calculations += 1
            else:
                checksum = None  # Don't calculate checksum for large/empty files
                self.skipped_checksums += 1

            return (directory, filename, checksum, modification_datetime, file_size)
        except PermissionError:
            # Permission denied - return None and report
            print(f"Permission denied: {file_path}")
            self.permission_errors += 1
            return None
        except OSError as e:
            print(f"Error accessing file {file_path}: {e}")
            return None
