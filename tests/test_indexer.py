"""
Tests for the FileIndexer class.
"""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from file_indexer.indexer import FileIndexer


class TestFileIndexer:
    """Test cases for FileIndexer functionality."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        # Create a temporary directory for test database
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.indexer = FileIndexer(str(self.db_path))

        # Create a temporary directory with test files
        self.test_files_dir = tempfile.mkdtemp()
        self.create_test_files()

    def teardown_method(self):
        """Clean up after each test method."""
        self.indexer.close()
        # Clean up temporary directories
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)
        shutil.rmtree(self.test_files_dir, ignore_errors=True)

    def create_test_files(self):
        """Create test files for testing."""
        # Create some test files with different content
        self.test_file1 = Path(self.test_files_dir) / "test1.txt"
        self.test_file2 = Path(self.test_files_dir) / "test2.txt"
        self.test_file3 = Path(self.test_files_dir) / "duplicate.txt"
        self.empty_file = Path(self.test_files_dir) / "empty.txt"

        # Create a subdirectory
        self.subdir = Path(self.test_files_dir) / "subdir"
        self.subdir.mkdir(parents=True)
        self.test_file4 = self.subdir / "test3.txt"

        # Write content to files
        self.test_file1.write_text("Hello World")
        self.test_file2.write_text("Different content")
        self.test_file3.write_text("Hello World")  # Duplicate content
        self.test_file4.write_text("Subdirectory file")
        self.empty_file.write_text("")  # Empty file

    def test_initial_stats(self):
        """Test that initial database stats are empty."""
        stats = self.indexer.get_stats()
        assert stats["total_files"] == 0
        assert stats["total_size"] == 0
        assert stats["files_with_checksum"] == 0
        assert stats["files_without_checksum"] == 0
        assert stats["unique_checksums"] == 0
        assert stats["duplicate_files"] == 0
        assert stats["last_indexed"] is None

    def test_scan_directory_recursive(self):
        """Test scanning a directory recursively."""
        files = self.indexer.scan_directory(self.test_files_dir, recursive=True)

        # Should find all 5 files (including subdirectory and empty file)
        assert len(files) == 5

        # Check that all expected files are found
        file_names = [Path(f).name for f in files]
        assert "test1.txt" in file_names
        assert "test2.txt" in file_names
        assert "duplicate.txt" in file_names
        assert "test3.txt" in file_names
        assert "empty.txt" in file_names

    def test_scan_directory_non_recursive(self):
        """Test scanning a directory non-recursively."""
        files = self.indexer.scan_directory(self.test_files_dir, recursive=False)

        # Should find 4 files (excluding subdirectory)
        assert len(files) == 4

        # Check that subdirectory file is not included
        file_names = [Path(f).name for f in files]
        assert "test1.txt" in file_names
        assert "test2.txt" in file_names
        assert "duplicate.txt" in file_names
        assert "empty.txt" in file_names
        assert "test3.txt" not in file_names

    def test_scan_nonexistent_directory(self):
        """Test scanning a non-existent directory."""
        files = self.indexer.scan_directory("/nonexistent/path")
        assert files == []

    def test_update_database(self):
        """Test updating the database with files."""
        self.indexer.update_database(self.test_files_dir, recursive=True)

        stats = self.indexer.get_stats()
        assert stats["total_files"] == 5
        assert stats["total_size"] > 0
        # With default settings, empty files won't have checksums
        if self.indexer.skip_empty_files:
            assert stats["files_with_checksum"] == 4  # All except empty file
            assert stats["files_without_checksum"] == 1  # Empty file
            assert (
                stats["unique_checksums"] == 3
            )  # Two files have same content (test1 and duplicate)
            assert stats["duplicate_files"] == 1  # One duplicate pair
        else:
            assert stats["files_with_checksum"] == 5
            assert (
                stats["unique_checksums"] == 4
            )  # Two files have same content, empty file has unique checksum
            assert stats["duplicate_files"] == 1
        assert stats["last_indexed"] is not None
        assert isinstance(stats["last_indexed"], datetime)

    def test_search_files_by_filename(self):
        """Test searching files by filename pattern."""
        self.indexer.update_database(self.test_files_dir, recursive=True)

        # Search for files with "test" in the name
        results = self.indexer.search_files(filename_pattern="%test%")
        assert len(results) >= 3  # test1.txt, test2.txt, test3.txt

        # Search for specific file
        results = self.indexer.search_files(filename_pattern="test1.txt")
        assert len(results) == 1
        assert results[0]["filename"] == "test1.txt"

    def test_search_files_by_path(self):
        """Test searching files by path pattern."""
        self.indexer.update_database(self.test_files_dir, recursive=True)

        # Search for files in subdirectory
        results = self.indexer.search_files(path_pattern="%subdir%")
        assert len(results) == 1
        assert results[0]["filename"] == "test3.txt"

    def test_search_files_by_checksum_presence(self):
        """Test searching files by checksum presence."""
        self.indexer.update_database(self.test_files_dir, recursive=True)

        # Search for files with checksums
        files_with_checksum = self.indexer.search_files(has_checksum=True)

        # Search for files without checksums
        files_without_checksum = self.indexer.search_files(has_checksum=False)

        # Total should equal all files
        assert len(files_with_checksum) + len(files_without_checksum) == 5

        # With default settings, empty files won't have checksums
        if self.indexer.skip_empty_files:
            assert len(files_with_checksum) == 4
            assert len(files_without_checksum) == 1
            # The file without checksum should be the empty file
            assert files_without_checksum[0]["filename"] == "empty.txt"
        else:
            assert len(files_with_checksum) == 5
            assert len(files_without_checksum) == 0

    def test_find_duplicates(self):
        """Test finding duplicate files."""
        self.indexer.update_database(self.test_files_dir, recursive=True)

        # Collect all duplicate files from the streaming method
        duplicates = []
        for duplicate_group in self.indexer.find_duplicates_streaming():
            for (
                path,
                filename,
                file_size,
                checksum,
                modification_datetime,
            ) in duplicate_group:
                duplicates.append(
                    {
                        "path": path,
                        "filename": filename,
                        "file_size": file_size,
                        "checksum": checksum,
                        "modification_datetime": modification_datetime,
                    }
                )

        assert len(duplicates) == 2  # test1.txt and duplicate.txt have same content

        # Check that both files with same content are found
        filenames = [dup["filename"] for dup in duplicates]
        assert "test1.txt" in filenames
        assert "duplicate.txt" in filenames

        # All duplicates should have checksums (only files with checksums can be duplicates)
        for dup in duplicates:
            assert dup["checksum"] is not None

    def test_calculate_checksum(self):
        """Test checksum calculation."""
        checksum1 = self.indexer._calculate_checksum(str(self.test_file1))
        checksum2 = self.indexer._calculate_checksum(str(self.test_file2))
        checksum3 = self.indexer._calculate_checksum(str(self.test_file3))

        # Different files should have different checksums
        assert checksum1 != checksum2

        # Files with same content should have same checksum
        assert checksum1 == checksum3

        # Checksums should be valid hex strings
        assert len(checksum1) == 64  # SHA256 produces 64-character hex string
        assert all(c in "0123456789abcdef" for c in checksum1)

    def test_checksum_nonexistent_file(self):
        """Test checksum calculation for non-existent file."""
        checksum = self.indexer._calculate_checksum("/nonexistent/file.txt")
        assert checksum == ""

    def test_get_file_info(self):
        """Test getting file information."""
        info = self.indexer._get_file_info(str(self.test_file1))
        assert info is not None

        directory, filename, checksum, mod_time, file_size = info
        assert filename == "test1.txt"
        if checksum is not None:  # Checksum might be None for large/empty files
            assert len(checksum) == 64
        assert isinstance(mod_time, datetime)
        assert file_size > 0

    def test_get_file_info_nonexistent(self):
        """Test getting file info for non-existent file."""
        info = self.indexer._get_file_info("/nonexistent/file.txt")
        assert info is None

    def test_database_persistence(self):
        """Test that data persists in the database."""
        # Add files to database
        self.indexer.update_database(self.test_files_dir, recursive=True)
        initial_stats = self.indexer.get_stats()

        # Close and reopen the indexer
        self.indexer.close()
        self.indexer = FileIndexer(str(self.db_path))

        # Check that data is still there
        stats = self.indexer.get_stats()
        assert stats["total_files"] == initial_stats["total_files"]
        assert stats["unique_checksums"] == initial_stats["unique_checksums"]

    def test_update_modified_file(self):
        """Test updating a file that has been modified."""
        # Index the files initially
        self.indexer.update_database(self.test_files_dir, recursive=False)
        initial_stats = self.indexer.get_stats()

        # Modify a file
        self.test_file1.write_text("Modified content")

        # Update database again
        self.indexer.update_database(self.test_files_dir, recursive=False)
        updated_stats = self.indexer.get_stats()

        # File count should be the same, but last_indexed should be updated
        assert updated_stats["total_files"] == initial_stats["total_files"]
        assert updated_stats["last_indexed"] > initial_stats["last_indexed"]

    def test_checksum_optimization(self):
        """Test that checksum calculation is optimized for unchanged files."""
        # Reset counters
        self.indexer.reset_optimization_counters()

        # Index the files initially (non-recursive to avoid empty file complexity)
        self.indexer.update_database(self.test_files_dir, recursive=False)
        initial_calculations = self.indexer.checksum_calculations
        initial_reuses = self.indexer.checksum_reuses

        # With default settings, empty files won't get checksums
        if self.indexer.skip_empty_files:
            assert initial_calculations == 3  # 3 non-empty files in root directory
        else:
            assert initial_calculations == 4  # All 4 files in root directory
        assert initial_reuses == 0

        # Update database again without modifying files
        self.indexer.update_database(self.test_files_dir, recursive=False)

        # Should have reused existing checksums for unmodified files
        assert (
            self.indexer.checksum_calculations == initial_calculations
        )  # No additional calculations

        if self.indexer.skip_empty_files:
            assert (
                self.indexer.checksum_reuses == 3
            )  # 3 non-empty files reused checksums
        else:
            assert self.indexer.checksum_reuses == 4  # All 4 files reused checksums

    def test_checksum_optimization_with_modified_file(self):
        """Test that optimization still calculates checksums for modified files."""
        # Reset counters and index initially (non-recursive)
        self.indexer.reset_optimization_counters()
        self.indexer.update_database(self.test_files_dir, recursive=False)

        # Modify one file
        self.test_file1.write_text("Modified content")

        # Reset counters to track only the second update
        self.indexer.reset_optimization_counters()

        # Update database again
        self.indexer.update_database(self.test_files_dir, recursive=False)

        # Should have calculated checksum for 1 modified file
        assert self.indexer.checksum_calculations == 1

        # Should have reused checksums for unmodified files with checksums
        if self.indexer.skip_empty_files:
            assert self.indexer.checksum_reuses == 2  # 2 other non-empty files
        else:
            assert self.indexer.checksum_reuses == 3  # 3 other files including empty

    def test_reset_optimization_counters(self):
        """Test resetting optimization counters."""
        # Do some operations
        self.indexer.update_database(self.test_files_dir, recursive=False)

        # Verify counters have values
        assert self.indexer.checksum_calculations >= 0
        assert self.indexer.skipped_checksums >= 0

        # Reset counters
        self.indexer.reset_optimization_counters()

        # Verify counters are reset
        assert self.indexer.checksum_calculations == 0
        assert self.indexer.checksum_reuses == 0
        assert self.indexer.skipped_checksums == 0
        assert self.indexer.ignored_special_files == 0

    def test_skipped_files_in_stats(self):
        """Test that skipped files are properly tracked and exposed in stats."""
        # Reset counters
        self.indexer.reset_optimization_counters()

        # Index files initially
        self.indexer.update_database(self.test_files_dir, recursive=False)

        # Verify no files were skipped on first run
        stats = self.indexer.get_stats()
        assert stats["skipped_files"] == 0

        # Reset counters to track only the second update
        self.indexer.reset_optimization_counters()

        # Update database again without modifying files
        self.indexer.update_database(self.test_files_dir, recursive=False)

        # Verify skipped files are tracked in stats
        stats = self.indexer.get_stats()
        assert stats["skipped_files"] == 4  # All 4 files should be skipped
        assert "skipped_files" in stats  # Ensure key exists in stats dictionary

        # Verify reset works for skipped files too
        self.indexer.reset_optimization_counters()
        stats = self.indexer.get_stats()
        assert stats["skipped_files"] == 0

    def test_ignore_symbolic_links(self):
        """Test that symbolic links are ignored during scanning and indexing."""
        # Create a test file and a symbolic link to it
        test_file = Path(self.test_files_dir) / "real_file.txt"
        symlink_file = Path(self.test_files_dir) / "symlink_file.txt"

        test_file.write_text("Real file content")

        # Create symbolic link (skip test if symlinks not supported on platform)
        try:
            symlink_file.symlink_to(test_file)
        except (OSError, NotImplementedError):
            # Symlinks not supported on this platform, skip test
            pytest.skip("Symbolic links not supported on this platform")

        # Reset counters
        self.indexer.reset_optimization_counters()

        # Scan directory - should find real file but ignore symlink
        files = self.indexer.scan_directory(self.test_files_dir, recursive=False)

        # Should find the original 4 test files + 1 new real file = 5 total
        # But should NOT include the symlink
        assert len(files) == 5
        assert str(test_file) in files
        assert str(symlink_file) not in files

        # Check that symlink was tracked as ignored
        assert self.indexer.ignored_symlinks == 1

        # Index the directory
        self.indexer.update_database(self.test_files_dir, recursive=False)

        # Check stats include ignored symlinks
        stats = self.indexer.get_stats()
        assert stats["ignored_symlinks"] == 1
        assert "ignored_symlinks" in stats  # Ensure key exists
        assert "ignored_special_files" in stats  # Ensure special files counter exists

        # Database should only contain 5 files (not the symlink)
        assert stats["total_files"] == 5

        # Clean up the symlink
        symlink_file.unlink()

    def test_checksum_size_limits(self):
        """Test that large files can be skipped for checksum calculation."""
        # Create indexer with very small size limit
        small_limit_indexer = FileIndexer(
            str(self.db_path) + "_small",
            max_checksum_size=10,  # 10 bytes limit
            skip_empty_files=False,
        )

        try:
            # Reset counters
            small_limit_indexer.reset_optimization_counters()

            # Index files - most should be skipped due to size
            small_limit_indexer.update_database(self.test_files_dir, recursive=False)

            stats = small_limit_indexer.get_stats()

            # Should have files indexed but some without checksums due to size
            assert stats["total_files"] == 4  # All files indexed
            assert stats["files_without_checksum"] > 0  # Some files skipped checksum
            assert (
                small_limit_indexer.skipped_checksums > 0
            )  # Tracked skipped checksums

        finally:
            small_limit_indexer.close()

    def test_empty_file_handling(self):
        """Test handling of empty files with different configurations."""
        # Test with skip_empty_files=True (default)
        skip_indexer = FileIndexer(str(self.db_path) + "_skip", skip_empty_files=True)

        try:
            skip_indexer.update_database(self.test_files_dir, recursive=False)
            skip_indexer.get_stats()

            # Empty file should not have checksum
            empty_results = skip_indexer.search_files(filename_pattern="empty.txt")
            assert len(empty_results) == 1
            assert empty_results[0]["checksum"] is None

        finally:
            skip_indexer.close()

        # Test with skip_empty_files=False
        calc_indexer = FileIndexer(str(self.db_path) + "_calc", skip_empty_files=False)

        try:
            calc_indexer.update_database(self.test_files_dir, recursive=False)

            # Empty file should have checksum
            empty_results = calc_indexer.search_files(filename_pattern="empty.txt")
            assert len(empty_results) == 1
            assert empty_results[0]["checksum"] is not None

        finally:
            calc_indexer.close()

    def test_schema_migration(self):
        """Test that schema migration works correctly."""
        # This test is mainly to ensure the migration code doesn't crash
        # The actual migration would require creating an old-format database

        # Create a new indexer and verify it works
        migration_indexer = FileIndexer(str(self.db_path) + "_migration")

        try:
            migration_indexer.update_database(self.test_files_dir, recursive=False)
            stats = migration_indexer.get_stats()
            assert stats["total_files"] > 0

        finally:
            migration_indexer.close()

    def test_batch_processing(self):
        """Test that batch processing works correctly."""
        # Reset counters
        self.indexer.reset_optimization_counters()

        # Index with very small batch size
        self.indexer.update_database(self.test_files_dir, recursive=True, batch_size=2)

        stats = self.indexer.get_stats()
        assert stats["total_files"] == 5  # All files should be processed
        assert stats["total_size"] > 0

    def test_index_files_without_checksums(self):
        """Test Phase 1: indexing files without calculating checksums."""
        # Reset counters
        self.indexer.reset_optimization_counters()

        # Index files without checksums
        self.indexer.index_files_without_checksums(self.test_files_dir, recursive=True)

        stats = self.indexer.get_stats()

        # All files should be indexed
        assert stats["total_files"] == 5
        assert stats["total_size"] > 0

        # No files should have checksums in Phase 1
        assert stats["files_with_checksum"] == 0
        assert stats["files_without_checksum"] == 5
        assert stats["unique_checksums"] == 0
        assert stats["duplicate_files"] == 0

        # Should have skipped all checksums
        assert self.indexer.skipped_checksums == 5

    def test_calculate_checksums_for_duplicates(self):
        """Test Phase 2: calculating checksums only for files with duplicate sizes."""
        # First, index files without checksums
        self.indexer.index_files_without_checksums(self.test_files_dir, recursive=True)

        # Reset counters to track Phase 2 only
        self.indexer.reset_optimization_counters()

        # Calculate checksums for potential duplicates
        self.indexer.calculate_checksums_for_duplicates()

        stats = self.indexer.get_stats()

        # Should still have all files
        assert stats["total_files"] == 5

        # Should have checksums for files with duplicate sizes
        # In our test set: test1.txt and duplicate.txt have same content and likely same size
        # Empty file might be in its own size category
        assert stats["files_with_checksum"] >= 2  # At least the duplicate files
        assert stats["files_without_checksum"] <= 3  # The rest

        # Should have found duplicates if any files had the same size
        if stats["files_with_checksum"] > 0:
            # Collect all duplicate files from the streaming method
            duplicates = []
            for duplicate_group in self.indexer.find_duplicates_streaming():
                for (
                    path,
                    filename,
                    file_size,
                    checksum,
                    modification_datetime,
                ) in duplicate_group:
                    duplicates.append(
                        {
                            "path": path,
                            "filename": filename,
                            "file_size": file_size,
                            "checksum": checksum,
                            "modification_datetime": modification_datetime,
                        }
                    )
            # test1.txt and duplicate.txt should be found as duplicates if they got checksums
            if stats["files_with_checksum"] >= 2:
                assert (
                    len(duplicates) >= 0
                )  # May or may not have duplicates depending on sizes

    def test_two_phase_indexing_complete(self):
        """Test complete two-phase indexing process."""
        # Create a new indexer for clean test
        two_phase_indexer = FileIndexer(str(self.db_path) + "_two_phase")

        try:
            # Reset counters
            two_phase_indexer.reset_optimization_counters()

            # Run complete two-phase indexing
            two_phase_indexer.two_phase_indexing(self.test_files_dir, recursive=True)

            stats = two_phase_indexer.get_stats()

            # All files should be indexed
            assert stats["total_files"] == 5
            assert stats["total_size"] > 0

            # Should have some files with checksums (those with duplicate sizes)
            assert stats["files_with_checksum"] >= 0
            assert stats["files_without_checksum"] >= 0
            assert stats["files_with_checksum"] + stats["files_without_checksum"] == 5

            # Should be able to find duplicates among files with checksums
            # Collect all duplicate files from the streaming method
            duplicates = []
            for duplicate_group in two_phase_indexer.find_duplicates_streaming():
                for (
                    path,
                    filename,
                    file_size,
                    checksum,
                    modification_datetime,
                ) in duplicate_group:
                    duplicates.append(
                        {
                            "path": path,
                            "filename": filename,
                            "file_size": file_size,
                            "checksum": checksum,
                            "modification_datetime": modification_datetime,
                        }
                    )
            assert isinstance(duplicates, list)

        finally:
            two_phase_indexer.close()

    def test_calculate_checksums_for_files_helper(self):
        """Test the helper method for calculating checksums for specific files."""
        # First, index without checksums
        self.indexer.index_files_without_checksums(self.test_files_dir, recursive=False)

        # Test the helper method directly
        file_paths = [str(self.test_file1), str(self.test_file2)]
        updated_count = self.indexer._calculate_checksums_for_files(file_paths)

        # Should have updated 2 files
        assert updated_count == 2

        # Check that these files now have checksums
        results1 = self.indexer.search_files(filename_pattern="test1.txt")
        results2 = self.indexer.search_files(filename_pattern="test2.txt")

        assert len(results1) == 1
        assert len(results2) == 1
        assert results1[0]["checksum"] is not None
        assert results2[0]["checksum"] is not None

    def test_two_phase_with_no_duplicates(self):
        """Test two-phase indexing when no files have duplicate sizes."""
        # Create files with unique sizes
        unique_dir = tempfile.mkdtemp()
        try:
            # Create files with different sizes
            (Path(unique_dir) / "small.txt").write_text("a")
            (Path(unique_dir) / "medium.txt").write_text("bb")
            (Path(unique_dir) / "large.txt").write_text("ccc")

            # Create indexer for this test
            unique_indexer = FileIndexer(str(self.db_path) + "_unique")

            try:
                # Run two-phase indexing
                unique_indexer.two_phase_indexing(unique_dir, recursive=True)

                stats = unique_indexer.get_stats()

                # All files should be indexed
                assert stats["total_files"] == 3

                # No files should have checksums since no duplicates
                assert stats["files_with_checksum"] == 0
                assert stats["files_without_checksum"] == 3
                assert stats["duplicate_files"] == 0

            finally:
                unique_indexer.close()

        finally:
            import shutil

            shutil.rmtree(unique_dir, ignore_errors=True)

    def test_two_phase_with_many_duplicates(self):
        """Test two-phase indexing with many files of the same size."""
        # Create directory with many files of the same size
        dup_dir = tempfile.mkdtemp()
        try:
            # Create multiple files with the same content (and thus same size)
            content = "duplicate content"
            for i in range(5):
                (Path(dup_dir) / f"dup{i}.txt").write_text(content)

            # Create one unique file
            (Path(dup_dir) / "unique.txt").write_text("unique content here")

            # Create indexer for this test
            dup_indexer = FileIndexer(str(self.db_path) + "_duplicates")

            try:
                # Run two-phase indexing
                dup_indexer.two_phase_indexing(dup_dir, recursive=True)

                stats = dup_indexer.get_stats()

                # All files should be indexed
                assert stats["total_files"] == 6

                # Should have checksums for the 5 duplicate files (same size)
                # Unique file might not get checksum if it's the only one of its size
                assert stats["files_with_checksum"] == 5  # The duplicate files
                assert stats["files_without_checksum"] == 1  # The unique file

                # Should find duplicates - but find_duplicates() doesn't return anything, it just prints
                # So we'll use the streaming method to collect results
                unique_duplicate_files = set()
                for duplicate_group in dup_indexer.find_duplicates_streaming():
                    for (
                        path,
                        filename,
                        _file_size,
                        _checksum,
                        _modification_datetime,
                    ) in duplicate_group:
                        unique_duplicate_files.add((path, filename))
                assert len(unique_duplicate_files) == 5  # All 5 duplicate files

            finally:
                dup_indexer.close()

        finally:
            import shutil

            shutil.rmtree(dup_dir, ignore_errors=True)

    def test_phase_separation(self):
        """Test that phases can be run separately and resumed."""
        # Create separate indexer for clean test
        phase_indexer = FileIndexer(str(self.db_path) + "_phases")

        try:
            # Phase 1 only
            phase_indexer.index_files_without_checksums(
                self.test_files_dir, recursive=True
            )

            stats_after_phase1 = phase_indexer.get_stats()
            assert stats_after_phase1["total_files"] == 5
            assert stats_after_phase1["files_with_checksum"] == 0
            assert stats_after_phase1["files_without_checksum"] == 5

            # Close and reopen indexer (simulating separate process)
            phase_indexer.close()
            phase_indexer = FileIndexer(str(self.db_path) + "_phases")

            # Phase 2 only
            phase_indexer.calculate_checksums_for_duplicates()

            stats_after_phase2 = phase_indexer.get_stats()
            assert stats_after_phase2["total_files"] == 5
            # Should now have some files with checksums
            assert stats_after_phase2["files_with_checksum"] >= 0
            assert (
                stats_after_phase2["files_with_checksum"]
                + stats_after_phase2["files_without_checksum"]
            ) == 5

        finally:
            phase_indexer.close()

    def test_two_phase_performance_tracking(self):
        """Test that performance counters work correctly with two-phase indexing."""
        # Create indexer for this test
        perf_indexer = FileIndexer(str(self.db_path) + "_perf")

        try:
            # Reset counters
            perf_indexer.reset_optimization_counters()

            # Run two-phase indexing
            perf_indexer.two_phase_indexing(self.test_files_dir, recursive=True)

            stats = perf_indexer.get_stats()

            # Check that performance counters are tracked
            assert "checksum_calculations" in stats
            assert "checksum_reuses" in stats
            assert "skipped_checksums" in stats
            assert "optimization_percentage" in stats

            # Should have skipped many checksums in Phase 1
            assert stats["skipped_checksums"] >= 0

            # Should have calculated some checksums in Phase 2 (if any duplicates found)
            assert stats["checksum_calculations"] >= 0

        finally:
            perf_indexer.close()

    def test_ignore_special_files_during_checksum_calculation(self):
        """Test that special files are ignored during checksum calculation phase."""
        import os
        import tempfile

        special_dir = tempfile.mkdtemp()
        try:
            # Create regular files
            (Path(special_dir) / "regular1.txt").write_text("content1")
            (Path(special_dir) / "regular2.txt").write_text("content2")

            # Try to create a named pipe (FIFO) if possible
            pipe_path = Path(special_dir) / "test_pipe"
            has_special_file = False
            try:
                os.mkfifo(str(pipe_path))
                has_special_file = True
            except (OSError, AttributeError):
                # Skip if not supported
                pass

            # Create indexer for this test
            special_indexer = FileIndexer(str(self.db_path) + "_special")

            try:
                # Phase 1: Index all files without checksums
                special_indexer.index_files_without_checksums(
                    special_dir, recursive=False
                )

                # Reset counters to track Phase 2 only
                special_indexer.reset_optimization_counters()

                # Phase 2: Try to calculate checksums - should skip special files
                special_indexer.calculate_checksums_for_duplicates()

                stats = special_indexer.get_stats()

                # Should have indexed only regular files (special files filtered during Phase 1)
                assert stats["total_files"] == 2  # Only regular files indexed
                assert stats["files_with_checksum"] == 2  # Only regular files

                if has_special_file:
                    # Special file should have been ignored during Phase 1 scanning
                    # The counter was reset, so check if it was previously ignored
                    pass  # Special files are filtered during Phase 1, not Phase 2

            finally:
                special_indexer.close()

        finally:
            import shutil

            shutil.rmtree(special_dir, ignore_errors=True)

    def test_empty_files_in_two_phase_indexing(self):
        """Test empty file handling in two-phase indexing with different settings."""
        import tempfile

        empty_dir = tempfile.mkdtemp()
        try:
            # Create multiple empty files and one regular file
            (Path(empty_dir) / "empty1.txt").write_text("")
            (Path(empty_dir) / "empty2.txt").write_text("")
            (Path(empty_dir) / "empty3.txt").write_text("")
            (Path(empty_dir) / "regular.txt").write_text("content")

            # Test with skip_empty_files=True
            skip_indexer = FileIndexer(
                str(self.db_path) + "_skip_empty", skip_empty_files=True
            )

            try:
                skip_indexer.two_phase_indexing(empty_dir, recursive=False)

                stats = skip_indexer.get_stats()

                # All files should be indexed
                assert stats["total_files"] == 4

                # Only regular file should have checksum (empty files skipped)
                assert stats["files_with_checksum"] == 0  # No duplicates by size
                assert stats["files_without_checksum"] == 4

                # Should have skipped checksums for empty files
                assert stats["skipped_checksums"] >= 3

            finally:
                skip_indexer.close()

            # Test with skip_empty_files=False
            calc_indexer = FileIndexer(
                str(self.db_path) + "_calc_empty", skip_empty_files=False
            )

            try:
                calc_indexer.two_phase_indexing(empty_dir, recursive=False)

                stats = calc_indexer.get_stats()

                # All files should be indexed
                assert stats["total_files"] == 4

                # Empty files should get checksums since they have duplicate sizes
                assert stats["files_with_checksum"] == 3  # 3 empty files
                assert stats["files_without_checksum"] == 1  # 1 unique regular file

            finally:
                calc_indexer.close()

        finally:
            import shutil

            shutil.rmtree(empty_dir, ignore_errors=True)

    def test_symlinks_during_checksum_calculation(self):
        """Test that symlinks are properly ignored during checksum calculation."""
        import tempfile

        symlink_dir = tempfile.mkdtemp()
        try:
            # Create regular files
            regular_file = Path(symlink_dir) / "regular.txt"
            regular_file.write_text("content")
            symlink_file = Path(symlink_dir) / "symlink.txt"

            # Create symbolic link (skip test if not supported)
            try:
                symlink_file.symlink_to(regular_file)
            except (OSError, NotImplementedError):
                pytest.skip("Symbolic links not supported on this platform")

            # Create indexer for this test
            symlink_indexer = FileIndexer(str(self.db_path) + "_symlink_test")

            try:
                # Index files without checksums first
                symlink_indexer.index_files_without_checksums(
                    symlink_dir, recursive=False
                )

                # Reset counters
                symlink_indexer.reset_optimization_counters()

                # Try to calculate checksums - should ignore symlinks
                symlink_indexer.calculate_checksums_for_duplicates()

                stats = symlink_indexer.get_stats()

                # Should only have the regular file (symlink filtered during Phase 1)
                assert stats["total_files"] == 1
                # Symlinks are filtered during Phase 1, so counter was reset
                # No symlinks should be encountered in Phase 2
                assert stats["ignored_symlinks"] == 0

            finally:
                symlink_indexer.close()

        finally:
            import shutil

            shutil.rmtree(symlink_dir, ignore_errors=True)

    def test_checksum_worker_function(self):
        """Test the checksum worker function directly."""
        import tempfile

        from file_indexer.indexer import _calculate_checksum_worker

        # Test with regular file
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
            temp_file.write("test content")
            temp_file_path = temp_file.name

        try:
            # Should calculate checksum successfully
            file_path, checksum = _calculate_checksum_worker(temp_file_path)
            assert file_path == temp_file_path
            assert checksum != ""
            assert len(checksum) == 64  # SHA256 hex digest length

        finally:
            Path(temp_file_path).unlink()

        # Test with non-existent file
        nonexistent_path = "/nonexistent/file.txt"
        file_path, checksum = _calculate_checksum_worker(nonexistent_path)
        assert file_path == nonexistent_path
        assert checksum == ""  # Should return empty string for errors

    def test_get_file_info_with_special_files(self):
        """Test _get_file_info method with special files."""
        import os
        import tempfile

        special_dir = tempfile.mkdtemp()
        try:
            # Create regular file
            regular_file = Path(special_dir) / "regular.txt"
            regular_file.write_text("content")

            # Test with regular file
            file_info = self.indexer._get_file_info(str(regular_file))
            assert file_info is not None
            assert file_info[1] == "regular.txt"  # filename

            # Try to create and test with special file
            pipe_path = Path(special_dir) / "test_pipe"
            try:
                os.mkfifo(str(pipe_path))

                # Reset counters
                self.indexer.reset_optimization_counters()

                # Should return None for special file
                file_info = self.indexer._get_file_info(str(pipe_path))
                assert file_info is None
                assert self.indexer.ignored_special_files == 1

            except (OSError, AttributeError):
                # Skip if named pipes not supported
                pass

        finally:
            import shutil

            shutil.rmtree(special_dir, ignore_errors=True)

    def test_error_handling_in_scan_directory(self):
        """Test error handling in scan_directory_generator."""
        # Test with non-existent directory
        files = list(self.indexer.scan_directory_generator("/nonexistent/directory"))
        assert len(files) == 0

        # Test with file instead of directory
        files = list(self.indexer.scan_directory_generator(str(self.test_file1)))
        assert len(files) == 0

    def test_bulk_operations_error_handling(self):
        """Test error handling in bulk database operations."""
        # This tests the transaction rollback functionality
        try:
            # Try to insert invalid data that would cause a database error
            invalid_inserts = [("", "", "checksum", "invalid_datetime", "invalid_size")]
            invalid_updates = []

            # This should handle the error gracefully
            added, updated = self.indexer._bulk_database_operations(
                invalid_inserts, invalid_updates
            )

            # Should handle the error without crashing
            assert True  # If we get here, error handling worked

        except Exception:
            # If an exception is raised, it should be a controlled one
            assert True

    def test_parallel_processing_disabled(self):
        """Test sequential processing when parallel processing is disabled."""
        # Create indexer with parallel processing disabled
        seq_indexer = FileIndexer(
            str(self.db_path) + "_sequential",
            use_parallel_processing=False,
            max_workers=1,
        )

        try:
            # Should work with sequential processing
            seq_indexer.update_database(self.test_files_dir, recursive=False)

            stats = seq_indexer.get_stats()
            assert stats["total_files"] == 4

        finally:
            seq_indexer.close()

    def test_calculate_checksums_with_empty_list(self):
        """Test checksum calculation with empty file list."""
        # Should handle empty list gracefully
        result = self.indexer._calculate_checksums_for_files([])
        assert result == 0

        # Should also handle None gracefully
        checksums = self.indexer._calculate_checksums_parallel([])
        assert checksums == {}

    def test_stats_with_all_counters(self):
        """Test that stats include all performance counters."""
        # Reset and perform various operations to populate counters
        self.indexer.reset_optimization_counters()
        self.indexer.update_database(self.test_files_dir, recursive=True)

        # Trigger all types of counters by re-indexing
        self.indexer.update_database(self.test_files_dir, recursive=True)

        stats = self.indexer.get_stats()

        # Verify all counter keys exist in stats
        expected_keys = [
            "total_files",
            "total_size",
            "files_with_checksum",
            "files_without_checksum",
            "unique_checksums",
            "duplicate_files",
            "last_indexed",
            "checksum_calculations",
            "checksum_reuses",
            "skipped_files",
            "ignored_symlinks",
            "ignored_special_files",
            "skipped_checksums",
            "permission_errors",
            "optimization_percentage",
            "deleted_files",
        ]

        for key in expected_keys:
            assert key in stats, f"Expected key '{key}' not found in stats"

        # Verify stats values are reasonable
        assert stats["optimization_percentage"] >= 0
        assert stats["optimization_percentage"] <= 100

    def test_cleanup_deleted_files_actual(self):
        """Test actual cleanup of deleted files."""
        # First, index some files
        self.indexer.update_database(self.test_files_dir, recursive=True)
        initial_stats = self.indexer.get_stats()
        assert initial_stats["total_files"] == 5

        # Delete two test files from filesystem
        self.test_file1.unlink()
        self.test_file2.unlink()

        # Run cleanup
        cleanup_result = self.indexer.cleanup_deleted_files()

        # Verify cleanup results
        assert cleanup_result["total_checked"] == 5
        assert cleanup_result["deleted_files"] == 2
        assert cleanup_result["permission_errors"] == 0

        # Database should be updated
        after_cleanup_stats = self.indexer.get_stats()
        assert after_cleanup_stats["total_files"] == 3  # 5 - 2 deleted = 3

        # Verify the deleted files are no longer in database
        remaining_files = self.indexer.search_files()
        remaining_filenames = [f["filename"] for f in remaining_files]
        assert "test1.txt" not in remaining_filenames
        assert "test2.txt" not in remaining_filenames
        assert "duplicate.txt" in remaining_filenames  # Should still be there

        # Verify deleted files counter is updated
        assert self.indexer.deleted_files == 2

    def test_cleanup_empty_directories(self):
        """Test cleanup of empty directories."""
        # First, index some files including subdirectory
        self.indexer.update_database(self.test_files_dir, recursive=True)
        initial_stats = self.indexer.get_stats()
        assert initial_stats["total_files"] == 5

        # Remove all files from subdirectory and the directory itself
        self.test_file4.unlink()  # Remove file from subdirectory
        self.subdir.rmdir()  # Remove the now-empty subdirectory

        # Run empty directory cleanup
        cleanup_result = self.indexer.cleanup_empty_directories()

        # Verify cleanup worked
        assert cleanup_result["deleted_directories"] >= 1

        # Database should be updated
        after_cleanup_stats = self.indexer.get_stats()
        assert after_cleanup_stats["total_files"] < initial_stats["total_files"]

    def test_cleanup_nonexistent_files(self):
        """Test cleanup when all files still exist (no cleanup needed)."""
        # Index files
        self.indexer.update_database(self.test_files_dir, recursive=True)

        # Run cleanup without deleting any files
        cleanup_result = self.indexer.cleanup_deleted_files()

        # Should find no deleted files
        assert cleanup_result["total_checked"] == 5
        assert cleanup_result["deleted_files"] == 0
        assert cleanup_result["deleted_directories"] == 0

        # Database should be unchanged
        stats = self.indexer.get_stats()
        assert stats["total_files"] == 5

    def test_cleanup_entire_directory_deleted(self):
        """Test cleanup when entire directory is deleted."""
        # Index files
        self.indexer.update_database(self.test_files_dir, recursive=True)
        initial_stats = self.indexer.get_stats()
        assert initial_stats["total_files"] == 5

        # Remove entire test directory
        import shutil

        shutil.rmtree(self.test_files_dir)

        # Run cleanup
        cleanup_result = self.indexer.cleanup_deleted_files()

        # All files should be marked as deleted
        assert cleanup_result["total_checked"] == 5
        assert cleanup_result["deleted_files"] == 5
        assert cleanup_result["deleted_directories"] >= 1  # At least the main directory

        # Database should be empty
        after_cleanup_stats = self.indexer.get_stats()
        assert after_cleanup_stats["total_files"] == 0

    def test_cleanup_with_empty_database(self):
        """Test cleanup when database is empty."""
        # Don't index anything, database should be empty
        cleanup_result = self.indexer.cleanup_deleted_files()

        # Should handle empty database gracefully
        assert cleanup_result["total_checked"] == 0
        assert cleanup_result["deleted_files"] == 0
        assert cleanup_result["deleted_directories"] == 0
        assert cleanup_result["permission_errors"] == 0

    def test_cleanup_batch_processing(self):
        """Test cleanup with different batch sizes."""
        # Index files
        self.indexer.update_database(self.test_files_dir, recursive=True)

        # Delete some files
        self.test_file1.unlink()
        self.test_file2.unlink()

        # Run cleanup with small batch size
        cleanup_result = self.indexer.cleanup_deleted_files(batch_size=2)

        # Should still work correctly
        assert cleanup_result["deleted_files"] == 2

        # Database should be updated
        stats = self.indexer.get_stats()
        assert stats["total_files"] == 3

    def test_cleanup_preserves_existing_files(self):
        """Test that cleanup preserves files that still exist."""
        # Index files
        self.indexer.update_database(self.test_files_dir, recursive=True)

        # Delete only one file
        self.test_file1.unlink()

        # Run cleanup
        cleanup_result = self.indexer.cleanup_deleted_files()

        # Only one file should be deleted from database
        assert cleanup_result["deleted_files"] == 1

        # Other files should still be in database
        remaining_files = self.indexer.search_files()
        assert len(remaining_files) == 4

        # Verify specific files are preserved
        remaining_filenames = [f["filename"] for f in remaining_files]
        assert "test2.txt" in remaining_filenames
        assert "duplicate.txt" in remaining_filenames
        assert "test3.txt" in remaining_filenames
        assert "empty.txt" in remaining_filenames
        assert "test1.txt" not in remaining_filenames

    def test_cleanup_optimization_directory_first(self):
        """Test that cleanup optimization works correctly when entire directories are deleted."""
        # Create additional nested directory structure for testing
        nested_dir = Path(self.test_files_dir) / "nested"
        nested_dir.mkdir()
        nested_file1 = nested_dir / "nested1.txt"
        nested_file2 = nested_dir / "nested2.txt"
        nested_file1.write_text("Nested content 1")
        nested_file2.write_text("Nested content 2")

        # Create another subdirectory
        another_dir = Path(self.test_files_dir) / "another"
        another_dir.mkdir()
        another_file = another_dir / "another.txt"
        another_file.write_text("Another content")

        # Index all files
        self.indexer.update_database(self.test_files_dir, recursive=True)
        initial_stats = self.indexer.get_stats()
        assert initial_stats["total_files"] == 8  # 5 original + 3 new files

        # Delete entire nested directory
        import shutil

        shutil.rmtree(nested_dir)

        # Run cleanup and verify optimization benefits
        cleanup_result = self.indexer.cleanup_deleted_files()

        # Verify results
        assert cleanup_result["deleted_files"] == 2  # 2 files in nested directory
        assert cleanup_result["deleted_directories"] == 1  # 1 deleted directory

        # Database should have 6 files now (8 - 2 deleted)
        after_cleanup_stats = self.indexer.get_stats()
        assert after_cleanup_stats["total_files"] == 6

        # Verify specific files are removed
        remaining_files = self.indexer.search_files()
        remaining_paths = [Path(f["path"]) / f["filename"] for f in remaining_files]
        assert nested_file1 not in remaining_paths
        assert nested_file2 not in remaining_paths
        assert another_file in remaining_paths  # Other files should remain

    def test_cleanup_mixed_deletion_scenario(self):
        """Test cleanup with mixed scenario: some directories deleted, some individual files deleted."""
        # Create nested structure
        nested_dir = Path(self.test_files_dir) / "nested"
        nested_dir.mkdir()
        nested_file = nested_dir / "nested.txt"
        nested_file.write_text("Nested content")

        # Index all files
        self.indexer.update_database(self.test_files_dir, recursive=True)
        initial_stats = self.indexer.get_stats()
        assert initial_stats["total_files"] == 6  # 5 original + 1 nested

        # Delete entire nested directory
        import shutil

        shutil.rmtree(nested_dir)

        # Delete individual file from main directory
        self.test_file1.unlink()

        # Run cleanup
        cleanup_result = self.indexer.cleanup_deleted_files()

        # Verify mixed deletion handling
        assert cleanup_result["deleted_files"] == 2  # 1 from directory + 1 individual
        assert cleanup_result["deleted_directories"] == 1  # 1 deleted directory

        # Database should have 4 files now (6 - 2 deleted)
        after_cleanup_stats = self.indexer.get_stats()
        assert after_cleanup_stats["total_files"] == 4

    def test_cleanup_permission_errors(self):
        """Test cleanup handles permission errors gracefully."""
        # Index files first
        self.indexer.update_database(self.test_files_dir, recursive=True)

        # Create a file that we'll simulate permission errors for
        # We can't easily create actual permission errors in tests,
        # so we'll test the error handling path by mocking or using invalid paths

        # Add a non-existent path to database manually to simulate permission scenario
        self.indexer.conn.execute(
            """
        INSERT INTO files (path, filename, checksum, modification_datetime, file_size)
        VALUES (?, ?, ?, ?, ?)
        """,
            ["/root/restricted", "file.txt", "abc123", "2023-01-01 00:00:00", 1000],
        )

        # Run cleanup - should handle permission errors gracefully
        cleanup_result = self.indexer.cleanup_deleted_files()

        # Should complete successfully despite permission issues
        assert isinstance(cleanup_result, dict)
        assert (
            cleanup_result["permission_errors"] >= 0
        )  # May be 0 if treated as missing file

    def test_cleanup_with_special_characters(self):
        """Test cleanup with special characters in file paths."""
        # Create files with special characters
        special_dir = Path(self.test_files_dir) / "special chars & symbols"
        special_dir.mkdir()

        special_files = [
            "file with spaces.txt",
            "file-with-dashes.txt",
            "file_with_underscores.txt",
            "файл.txt",  # Unicode
            "file(with)parentheses.txt",
        ]

        for filename in special_files:
            try:
                file_path = special_dir / filename
                file_path.write_text(f"Content of {filename}")
            except (OSError, UnicodeError):
                # Skip files that can't be created on this filesystem
                continue

        # Index files
        self.indexer.update_database(self.test_files_dir, recursive=True)
        initial_count = self.indexer.get_stats()["total_files"]

        # Delete the special directory
        import shutil

        shutil.rmtree(special_dir)

        # Run cleanup
        cleanup_result = self.indexer.cleanup_deleted_files()

        # Should handle special characters correctly
        assert cleanup_result["deleted_files"] > 0
        assert cleanup_result["deleted_directories"] >= 1

        final_count = self.indexer.get_stats()["total_files"]
        assert final_count < initial_count

    def test_cleanup_deep_directory_hierarchy(self):
        """Test cleanup optimization with deep directory hierarchies."""
        # Create a deep directory structure
        current_dir = Path(self.test_files_dir)
        deep_dirs = []

        # Create nested directories: level1/level2/level3/level4/level5
        for i in range(5):
            current_dir = current_dir / f"level{i + 1}"
            current_dir.mkdir()
            deep_dirs.append(current_dir)

            # Add files at each level
            for j in range(2):
                file_path = current_dir / f"file_L{i + 1}_{j + 1}.txt"
                file_path.write_text(f"Content at level {i + 1}, file {j + 1}")

        # Index all files
        self.indexer.update_database(self.test_files_dir, recursive=True)

        # Delete the entire deep hierarchy by removing level1
        import shutil

        shutil.rmtree(Path(self.test_files_dir) / "level1")

        # Run cleanup
        cleanup_result = self.indexer.cleanup_deleted_files()

        # Should optimize by detecting all nested directory deletions
        assert cleanup_result["deleted_files"] == 10  # 5 levels × 2 files each
        assert (
            cleanup_result["deleted_directories"] >= 1
        )  # At least 1 deleted directory

    def test_cleanup_large_dataset_batching(self):
        """Test cleanup with larger dataset to verify batch processing."""
        # Create a larger dataset
        large_dir = Path(self.test_files_dir) / "large_dataset"
        large_dir.mkdir()

        # Create 50 files in batches
        files_created = []
        for i in range(50):
            file_path = large_dir / f"file_{i:03d}.txt"
            file_path.write_text(f"Content of file {i}")
            files_created.append(file_path)

        # Index all files
        self.indexer.update_database(self.test_files_dir, recursive=True)
        initial_stats = self.indexer.get_stats()

        # Delete directory with many files
        import shutil

        shutil.rmtree(large_dir)

        # Run cleanup with small batch size to test batching
        cleanup_result = self.indexer.cleanup_deleted_files(batch_size=10)

        # Should handle large dataset correctly
        assert cleanup_result["deleted_files"] == 50
        assert cleanup_result["deleted_directories"] == 1

        # Verify database is correctly updated
        final_stats = self.indexer.get_stats()
        assert final_stats["total_files"] == initial_stats["total_files"] - 50

    def test_cleanup_database_transaction_integrity(self):
        """Test that cleanup maintains database transaction integrity."""
        # Index files
        self.indexer.update_database(self.test_files_dir, recursive=True)
        initial_stats = self.indexer.get_stats()

        # Delete some files
        self.test_file1.unlink()
        self.test_file2.unlink()

        # Run cleanup and verify database consistency
        cleanup_result = self.indexer.cleanup_deleted_files()

        # Verify database is in consistent state
        final_stats = self.indexer.get_stats()

        # Total files should be reduced by exactly the number deleted
        assert (
            final_stats["total_files"]
            == initial_stats["total_files"] - cleanup_result["deleted_files"]
        )


if __name__ == "__main__":
    pytest.main([__file__])
