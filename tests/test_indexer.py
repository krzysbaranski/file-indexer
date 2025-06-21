"""
Tests for the FileIndexer class.
"""

import os
import tempfile
from datetime import datetime

import pytest

from file_indexer.indexer import FileIndexer


class TestFileIndexer:
    """Test cases for FileIndexer functionality."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        # Create a temporary directory for test database
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        self.indexer = FileIndexer(self.db_path)

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
        self.test_file1 = os.path.join(self.test_files_dir, "test1.txt")
        self.test_file2 = os.path.join(self.test_files_dir, "test2.txt")
        self.test_file3 = os.path.join(self.test_files_dir, "duplicate.txt")

        # Create a subdirectory
        self.subdir = os.path.join(self.test_files_dir, "subdir")
        os.makedirs(self.subdir)
        self.test_file4 = os.path.join(self.subdir, "test3.txt")

        # Write content to files
        with open(self.test_file1, "w") as f:
            f.write("Hello World")

        with open(self.test_file2, "w") as f:
            f.write("Different content")

        with open(self.test_file3, "w") as f:
            f.write("Hello World")  # Duplicate content

        with open(self.test_file4, "w") as f:
            f.write("Subdirectory file")

    def test_initial_stats(self):
        """Test that initial database stats are empty."""
        stats = self.indexer.get_stats()
        assert stats["total_files"] == 0
        assert stats["total_size"] == 0
        assert stats["unique_checksums"] == 0
        assert stats["duplicate_files"] == 0
        assert stats["last_indexed"] is None

    def test_scan_directory_recursive(self):
        """Test scanning a directory recursively."""
        files = self.indexer.scan_directory(self.test_files_dir, recursive=True)

        # Should find all 4 files (including subdirectory)
        assert len(files) == 4

        # Check that all expected files are found
        file_names = [os.path.basename(f) for f in files]
        assert "test1.txt" in file_names
        assert "test2.txt" in file_names
        assert "duplicate.txt" in file_names
        assert "test3.txt" in file_names

    def test_scan_directory_non_recursive(self):
        """Test scanning a directory non-recursively."""
        files = self.indexer.scan_directory(self.test_files_dir, recursive=False)

        # Should find only 3 files (excluding subdirectory)
        assert len(files) == 3

        # Check that subdirectory file is not included
        file_names = [os.path.basename(f) for f in files]
        assert "test1.txt" in file_names
        assert "test2.txt" in file_names
        assert "duplicate.txt" in file_names
        assert "test3.txt" not in file_names

    def test_scan_nonexistent_directory(self):
        """Test scanning a non-existent directory."""
        files = self.indexer.scan_directory("/nonexistent/path")
        assert files == []

    def test_update_database(self):
        """Test updating the database with files."""
        self.indexer.update_database(self.test_files_dir, recursive=True)

        stats = self.indexer.get_stats()
        assert stats["total_files"] == 4
        assert stats["total_size"] > 0
        assert stats["unique_checksums"] == 3  # Two files have same content
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

    def test_find_duplicates(self):
        """Test finding duplicate files."""
        self.indexer.update_database(self.test_files_dir, recursive=True)

        duplicates = self.indexer.find_duplicates()
        assert len(duplicates) == 2  # test1.txt and duplicate.txt have same content

        # Check that both files with same content are found
        filenames = [dup["filename"] for dup in duplicates]
        assert "test1.txt" in filenames
        assert "duplicate.txt" in filenames

    def test_calculate_checksum(self):
        """Test checksum calculation."""
        checksum1 = self.indexer._calculate_checksum(self.test_file1)
        checksum2 = self.indexer._calculate_checksum(self.test_file2)
        checksum3 = self.indexer._calculate_checksum(self.test_file3)

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
        info = self.indexer._get_file_info(self.test_file1)
        assert info is not None

        directory, filename, checksum, mod_time, file_size = info
        assert filename == "test1.txt"
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
        self.indexer = FileIndexer(self.db_path)

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
        with open(self.test_file1, "w") as f:
            f.write("Modified content")

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
        
        # Index the files initially
        self.indexer.update_database(self.test_files_dir, recursive=False)
        initial_calculations = self.indexer.checksum_calculations
        initial_reuses = self.indexer.checksum_reuses
        
        # All files should have required checksum calculations on first run
        assert initial_calculations == 3  # 3 files in root directory
        assert initial_reuses == 0
        
        # Update database again without modifying files
        self.indexer.update_database(self.test_files_dir, recursive=False)
        
        # Should have reused existing checksums for unmodified files
        assert self.indexer.checksum_calculations == initial_calculations  # No additional calculations
        assert self.indexer.checksum_reuses == 3  # All 3 files reused checksums
        
        # Check optimization statistics
        stats = self.indexer.get_stats()
        assert stats["checksum_calculations"] == 3
        assert stats["checksum_reuses"] == 3
        assert stats["optimization_percentage"] == 50.0  # 3/(3+3) = 50%

    def test_checksum_optimization_with_modified_file(self):
        """Test that optimization still calculates checksums for modified files."""
        # Reset counters and index initially
        self.indexer.reset_optimization_counters()
        self.indexer.update_database(self.test_files_dir, recursive=False)
        
        # Modify one file
        with open(self.test_file1, "w") as f:
            f.write("Modified content")
        
        # Reset counters to track only the second update
        self.indexer.reset_optimization_counters()
        
        # Update database again
        self.indexer.update_database(self.test_files_dir, recursive=False)
        
        # Should have calculated checksum for 1 modified file and reused 2 others
        assert self.indexer.checksum_calculations == 1
        assert self.indexer.checksum_reuses == 2
        
        stats = self.indexer.get_stats()
        assert stats["optimization_percentage"] == round((2/3) * 100, 2)  # 2 reused out of 3 total

    def test_reset_optimization_counters(self):
        """Test resetting optimization counters."""
        # Do some operations
        self.indexer.update_database(self.test_files_dir, recursive=False)
        
        # Verify counters have values
        assert self.indexer.checksum_calculations > 0
        
        # Reset counters
        self.indexer.reset_optimization_counters()
        
        # Verify counters are reset
        assert self.indexer.checksum_calculations == 0
        assert self.indexer.checksum_reuses == 0


if __name__ == "__main__":
    pytest.main([__file__])
