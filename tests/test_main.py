"""
Tests for the file_indexer.__main__ module.
"""

from unittest.mock import patch

import pytest


class TestMain:
    """Test cases for __main__ module."""

    @patch("file_indexer.cli.main")
    def test_main_delegates_to_cli(self, mock_cli_main):
        """Test that __main__.main() delegates to cli.main()."""
        from file_indexer.__main__ import main

        # Call the main function
        main()

        # Verify that cli.main() was called
        mock_cli_main.assert_called_once()

    def test_main_module_exists(self):
        """Test that __main__ module can be imported."""
        # Just test that the module can be imported without error
        import file_indexer.__main__

        # Verify that the main function exists
        assert hasattr(file_indexer.__main__, "main")
        assert callable(file_indexer.__main__.main)


if __name__ == "__main__":
    pytest.main([__file__])
