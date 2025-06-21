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

        duplicates = self.indexer.find_duplicates()
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
            stats = skip_indexer.get_stats()

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
            stats = calc_indexer.get_stats()

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


if __name__ == "__main__":
    pytest.main([__file__])
