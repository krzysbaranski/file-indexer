"""
Tests for the file_indexer.cli module.
"""

import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys
import argparse

from file_indexer.cli import main, parse_size


class TestCLI:
    """Test cases for CLI functions."""

    def test_parse_size_bytes(self):
        """Test parsing size strings in bytes."""
        assert parse_size("100") == 100
        assert parse_size("100B") == 100
        assert parse_size("0") == 0

    def test_parse_size_kilobytes(self):
        """Test parsing size strings in kilobytes."""
        assert parse_size("1K") == 1024
        assert parse_size("1KB") == 1024
        assert parse_size("2KB") == 2048
        assert parse_size("1.5KB") == 1536

    def test_parse_size_megabytes(self):
        """Test parsing size strings in megabytes."""
        assert parse_size("1M") == 1024 * 1024
        assert parse_size("1MB") == 1024 * 1024
        assert parse_size("100MB") == 100 * 1024 * 1024
        assert parse_size("1.5MB") == int(1.5 * 1024 * 1024)

    def test_parse_size_gigabytes(self):
        """Test parsing size strings in gigabytes."""
        assert parse_size("1G") == 1024 * 1024 * 1024
        assert parse_size("1GB") == 1024 * 1024 * 1024
        assert parse_size("2GB") == 2 * 1024 * 1024 * 1024

    def test_parse_size_terabytes(self):
        """Test parsing size strings in terabytes."""
        assert parse_size("1T") == 1024 * 1024 * 1024 * 1024
        assert parse_size("1TB") == 1024 * 1024 * 1024 * 1024

    def test_parse_size_invalid(self):
        """Test parsing invalid size strings."""
        with pytest.raises(ValueError):
            parse_size("invalid")
        
        with pytest.raises(ValueError):
            parse_size("100XB")  # Invalid unit
        
        with pytest.raises(ValueError):
            parse_size("abc123")  # Invalid format

    def test_parse_size_case_insensitive(self):
        """Test that size parsing is case insensitive."""
        assert parse_size("100mb") == 100 * 1024 * 1024
        assert parse_size("1gb") == 1024 * 1024 * 1024
        assert parse_size("1Mb") == 1024 * 1024

    @patch('file_indexer.cli.FileIndexer')
    def test_main_scan_operation(self, mock_indexer_class):
        """Test main function with scan operation."""
        # Mock the FileIndexer class
        mock_indexer = MagicMock()
        mock_indexer_class.return_value = mock_indexer
        
        # Test arguments
        test_args = [
            'file-indexer',  # Program name
            '--scan', '/test/dir',
            '--db', 'test.db'
        ]
        
        with patch.object(sys, 'argv', test_args):
            try:
                main()
                # Verify that FileIndexer was called with correct arguments
                mock_indexer_class.assert_called_once()
                mock_indexer.update_database.assert_called_once()
                mock_indexer.close.assert_called_once()
            except SystemExit as e:
                # Exit code 0 is success
                assert e.code == 0

    @patch('file_indexer.cli.FileIndexer')
    def test_main_stats_operation(self, mock_indexer_class):
        """Test main function with stats operation."""
        # Mock the FileIndexer class
        mock_indexer = MagicMock()
        mock_indexer.get_stats.return_value = {
            'total_files': 100,
            'total_size': 1024000,
            'files_with_checksum': 90,
            'files_without_checksum': 10,
            'unique_checksums': 85,
            'duplicate_files': 5,
            'last_indexed': '2024-01-01 12:00:00',
            'checksum_calculations': 0,
            'checksum_reuses': 0,
            'optimization_percentage': 0
        }
        mock_indexer_class.return_value = mock_indexer
        
        # Test arguments
        test_args = [
            'file-indexer',
            '--stats',
            '--db', 'test.db'
        ]
        
        with patch.object(sys, 'argv', test_args):
            try:
                main()
                # Verify that get_stats was called
                mock_indexer.get_stats.assert_called_once()
                mock_indexer.close.assert_called_once()
            except SystemExit as e:
                # Exit code 0 is success
                assert e.code == 0

    @patch('file_indexer.cli.FileIndexer')
    def test_main_two_phase_operation(self, mock_indexer_class):
        """Test main function with two-phase operation."""
        # Mock the FileIndexer class
        mock_indexer = MagicMock()
        mock_indexer_class.return_value = mock_indexer
        
        # Test arguments
        test_args = [
            'file-indexer',
            '--two-phase', '/test/dir',
            '--db', 'test.db'
        ]
        
        with patch.object(sys, 'argv', test_args):
            try:
                main()
                # Verify that two_phase_indexing was called
                mock_indexer.two_phase_indexing.assert_called_once()
                mock_indexer.close.assert_called_once()
            except SystemExit as e:
                # Exit code 0 is success
                assert e.code == 0

    def test_main_help(self):
        """Test that help argument works."""
        test_args = ['file-indexer', '--help']
        
        with patch.object(sys, 'argv', test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()
            # Help should exit with code 0
            assert exc_info.value.code == 0


if __name__ == "__main__":
    pytest.main([__file__]) 