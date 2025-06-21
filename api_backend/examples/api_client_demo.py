#!/usr/bin/env python3
"""
Demo script showing how to interact with the File Indexer API.

This script demonstrates various API endpoints and how to use them
programmatically with the requests library.
"""

import json
import time
from typing import Any, Dict

import requests


class FileIndexerClient:
    """Simple client for the File Indexer API."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        """Initialize the client with the API base URL."""
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

    def health_check(self) -> Dict[str, Any]:
        """Check API health."""
        response = self.session.get(f"{self.base_url}/health/")
        response.raise_for_status()
        return response.json()

    def search_files(
        self,
        filename_pattern: str = None,
        path_pattern: str = None,
        has_checksum: bool = None,
        min_size: int = None,
        max_size: int = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Search for files using GET parameters."""
        params = {"limit": limit, "offset": offset}

        if filename_pattern:
            params["filename_pattern"] = filename_pattern
        if path_pattern:
            params["path_pattern"] = path_pattern
        if has_checksum is not None:
            params["has_checksum"] = has_checksum
        if min_size is not None:
            params["min_size"] = min_size
        if max_size is not None:
            params["max_size"] = max_size

        response = self.session.get(f"{self.base_url}/search/", params=params)
        response.raise_for_status()
        return response.json()

    def search_files_advanced(self, search_request: Dict[str, Any]) -> Dict[str, Any]:
        """Search for files using POST with advanced parameters."""
        response = self.session.post(f"{self.base_url}/search/", json=search_request)
        response.raise_for_status()
        return response.json()

    def find_duplicates(self, min_group_size: int = 2) -> Dict[str, Any]:
        """Find duplicate files."""
        params = {"min_group_size": min_group_size}
        response = self.session.get(f"{self.base_url}/duplicates/", params=params)
        response.raise_for_status()
        return response.json()

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        response = self.session.get(f"{self.base_url}/stats/")
        response.raise_for_status()
        return response.json()

    def get_visualization_data(self) -> Dict[str, Any]:
        """Get visualization data."""
        response = self.session.get(f"{self.base_url}/stats/visualization")
        response.raise_for_status()
        return response.json()


def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format."""
    if size_bytes == 0:
        return "0 B"

    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


def main():
    """Main demo function."""
    # Initialize client
    client = FileIndexerClient()

    print("File Indexer API Demo")
    print("=" * 50)

    try:
        # 1. Health check
        print("\n1. Health Check")
        health = client.health_check()
        print(f"Status: {health['status']}")
        print(f"Database connected: {health['database_connected']}")
        print(f"Total files: {health['total_files']:,}")

        if health["status"] != "healthy":
            print("API is not healthy, exiting...")
            return

        # 2. Database statistics
        print("\n2. Database Statistics")
        stats = client.get_stats()
        print(f"Total files: {stats['total_files']:,}")
        print(f"Total size: {format_file_size(stats['total_size'])}")
        print(f"Files with checksums: {stats['files_with_checksums']:,}")
        print(f"Files without checksums: {stats['files_without_checksums']:,}")
        print(f"Duplicate files: {stats['duplicate_files']:,}")
        print(f"Duplicate groups: {stats['duplicate_groups']:,}")
        print(f"Unique directories: {stats['unique_directories']:,}")

        # 3. Search examples
        print("\n3. Search Examples")

        # Search for Python files
        print("\n3a. Searching for Python files (*.py)...")
        python_files = client.search_files(filename_pattern="%.py", limit=5)
        print(f"Found {python_files['total_count']} Python files (showing first 5):")
        for file in python_files["files"]:
            print(
                f"  - {file['path']}/{file['filename']} ({format_file_size(file['file_size'])})"
            )

        # Search for large files
        print("\n3b. Searching for files larger than 10MB...")
        large_files = client.search_files(min_size=10 * 1024 * 1024, limit=5)
        print(f"Found {large_files['total_count']} large files (showing first 5):")
        for file in large_files["files"]:
            print(
                f"  - {file['path']}/{file['filename']} ({format_file_size(file['file_size'])})"
            )

        # Search for files without checksums
        print("\n3c. Searching for files without checksums...")
        no_checksum_files = client.search_files(has_checksum=False, limit=5)
        print(
            f"Found {no_checksum_files['total_count']} files without checksums (showing first 5):"
        )
        for file in no_checksum_files["files"]:
            print(
                f"  - {file['path']}/{file['filename']} ({format_file_size(file['file_size'])})"
            )

        # 4. Advanced search with POST
        print("\n4. Advanced Search (POST)")
        advanced_search = {
            "filename_pattern": "%.pdf",
            "min_size": 100000,  # 100KB
            "max_size": 10000000,  # 10MB
            "limit": 3,
        }
        pdf_files = client.search_files_advanced(advanced_search)
        print(
            f"Found {pdf_files['total_count']} PDF files between 100KB and 10MB (showing first 3):"
        )
        for file in pdf_files["files"]:
            print(
                f"  - {file['path']}/{file['filename']} ({format_file_size(file['file_size'])})"
            )

        # 5. Find duplicates
        print("\n5. Duplicate Files")
        duplicates = client.find_duplicates()
        print(
            f"Found {duplicates['total_groups']} duplicate groups with {duplicates['total_duplicate_files']} total duplicate files"
        )

        if duplicates["duplicate_groups"]:
            print("Top 3 duplicate groups:")
            for i, group in enumerate(duplicates["duplicate_groups"][:3]):
                print(
                    f"\n  Group {i + 1}: {group['file_count']} files, {format_file_size(group['file_size'])} each"
                )
                print(f"  Checksum: {group['checksum'][:16]}...")
                for file in group["files"][:3]:  # Show first 3 files in group
                    print(f"    - {file['path']}/{file['filename']}")
                if len(group["files"]) > 3:
                    print(f"    ... and {len(group['files']) - 3} more files")

        # 6. Visualization data
        print("\n6. Visualization Data")
        viz_data = client.get_visualization_data()

        print("\nFile size distribution:")
        for dist in viz_data["size_distribution"]:
            print(
                f"  {dist['size_range']}: {dist['count']:,} files ({format_file_size(dist['total_size'])})"
            )

        print(f"\nTop file extensions:")
        for ext in viz_data["extension_stats"][:5]:
            print(
                f"  {ext['extension']}: {ext['count']:,} files ({format_file_size(ext['total_size'])})"
            )

        print(
            f"\nModification timeline: {len(viz_data['modification_timeline'])} data points"
        )

        print("\n" + "=" * 50)
        print("Demo completed successfully!")

    except requests.exceptions.ConnectionError:
        print(f"Error: Could not connect to API at {client.base_url}")
        print("Make sure the API server is running and accessible.")
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e}")
        if hasattr(e.response, "text"):
            print(f"Response: {e.response.text}")
    except Exception as e:
        print(f"Unexpected error: {e}")


if __name__ == "__main__":
    main()
