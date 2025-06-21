"""
Tests for the file_indexer.utils module.
"""

import pytest
from file_indexer.utils import format_size


class TestUtils:
    """Test cases for utility functions."""

    def test_format_size_zero(self):
        """Test formatting zero bytes."""
        assert format_size(0) == "0 B"

    def test_format_size_bytes(self):
        """Test formatting file sizes in bytes."""
        assert format_size(1) == "1.0 B"
        assert format_size(512) == "512.0 B"
        assert format_size(1023) == "1023.0 B"

    def test_format_size_kilobytes(self):
        """Test formatting file sizes in kilobytes."""
        assert format_size(1024) == "1.0 KB"
        assert format_size(1536) == "1.5 KB"
        assert format_size(2048) == "2.0 KB"
        assert format_size(1048575) == "1024.0 KB"

    def test_format_size_megabytes(self):
        """Test formatting file sizes in megabytes."""
        assert format_size(1048576) == "1.0 MB"
        assert format_size(1572864) == "1.5 MB"
        assert format_size(2097152) == "2.0 MB"
        assert format_size(1073741823) == "1024.0 MB"

    def test_format_size_gigabytes(self):
        """Test formatting file sizes in gigabytes."""
        assert format_size(1073741824) == "1.0 GB"
        assert format_size(1610612736) == "1.5 GB"
        assert format_size(2147483648) == "2.0 GB"
        assert format_size(1099511627775) == "1024.0 GB"

    def test_format_size_terabytes(self):
        """Test formatting file sizes in terabytes."""
        assert format_size(1099511627776) == "1.0 TB"
        assert format_size(1649267441664) == "1.5 TB"
        assert format_size(2199023255552) == "2.0 TB"

    def test_format_size_large_values(self):
        """Test formatting very large file sizes."""
        # Should cap at TB
        very_large = 1024 * 1024 * 1024 * 1024 * 1024  # 1 PB in bytes
        result = format_size(very_large)
        assert result.endswith(" TB")
        assert "1024.0" in result

    def test_format_size_edge_cases(self):
        """Test edge cases for format_size function."""
        # Test exact boundary values
        assert format_size(1024) == "1.0 KB"
        assert format_size(1024 * 1024) == "1.0 MB"
        assert format_size(1024 * 1024 * 1024) == "1.0 GB"
        assert format_size(1024 * 1024 * 1024 * 1024) == "1.0 TB"

    def test_format_size_fractional(self):
        """Test formatting file sizes with fractional results."""
        # Test values that result in decimal places
        assert format_size(1024 + 512) == "1.5 KB"
        assert format_size(1048576 + 524288) == "1.5 MB"
        assert format_size(1073741824 + 536870912) == "1.5 GB"


if __name__ == "__main__":
    pytest.main([__file__])
