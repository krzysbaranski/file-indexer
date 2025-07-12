#!/usr/bin/env python3
"""
Simple test script to verify the checksum calculation fix.
"""

import sqlite3


def create_test_database():
    """Create a test database with files that simulate the issue."""
    conn = sqlite3.connect(":memory:")

    # Create the files table
    conn.execute("""
    CREATE TABLE files (
        path TEXT NOT NULL,
        filename TEXT NOT NULL,
        file_size INTEGER NOT NULL,
        checksum TEXT,
        indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        modification_datetime TIMESTAMP,
        PRIMARY KEY (path, filename)
    )
    """)

    # Insert test data that simulates the issue
    # File size 1000 has 3 files: 2 with checksums, 1 without
    # File size 2000 has 2 files: both without checksums
    # File size 3000 has 1 file: without checksum (should be ignored)
    test_data = [
        # Size 1000 - should be included because it has files without checksums
        ("/path1", "file1.txt", 1000, "abc123", "2024-01-01 10:00:00"),
        ("/path2", "file2.txt", 1000, "def456", "2024-01-01 10:00:00"),
        ("/path3", "file3.txt", 1000, None, "2024-01-01 10:00:00"),
        # Size 2000 - should be included because all files lack checksums
        ("/path4", "file4.txt", 2000, None, "2024-01-01 10:00:00"),
        ("/path5", "file5.txt", 2000, None, "2024-01-01 10:00:00"),
        # Size 3000 - should be ignored because only one file
        ("/path6", "file6.txt", 3000, None, "2024-01-01 10:00:00"),
        # Size 4000 - should be ignored because all files have checksums
        ("/path7", "file7.txt", 4000, "ghi789", "2024-01-01 10:00:00"),
        ("/path8", "file8.txt", 4000, "jkl012", "2024-01-01 10:00:00"),
    ]

    conn.executemany(
        """
    INSERT INTO files (path, filename, file_size, checksum, modification_datetime)
    VALUES (?, ?, ?, ?, ?)
    """,
        test_data,
    )

    conn.commit()
    return conn


def test_old_query():
    """Test the old query logic."""
    print("=== Testing OLD query logic ===")
    conn = create_test_database()

    # Old query - only finds sizes where ALL files have checksum IS NULL
    old_query = """
    SELECT file_size, COUNT(*) as file_count
    FROM files
    WHERE checksum IS NULL
    GROUP BY file_size
    HAVING COUNT(*) > 1
    ORDER BY file_size
    """

    results = conn.execute(old_query).fetchall()
    print(f"Old query found {len(results)} file sizes:")
    for size, count in results:
        print(f"  Size {size}: {count} files")

    conn.close()


def test_new_query():
    """Test the new query logic."""
    print("\n=== Testing NEW query logic ===")
    conn = create_test_database()

    # New query - finds sizes where there are multiple files AND at least one has checksum IS NULL
    new_query = """
    SELECT file_size, COUNT(*) as file_count
    FROM files
    GROUP BY file_size
    HAVING COUNT(*) > 1 AND SUM(CASE WHEN checksum IS NULL THEN 1 ELSE 0 END) > 0
    ORDER BY file_size
    """

    results = conn.execute(new_query).fetchall()
    print(f"New query found {len(results)} file sizes:")
    for size, count in results:
        print(f"  Size {size}: {count} files")

    # Show details for each size
    for size, _count in results:
        print(f"\nDetails for size {size}:")
        files = conn.execute(
            """
        SELECT path, filename, checksum IS NULL as needs_checksum
        FROM files WHERE file_size = ?
        ORDER BY path, filename
        """,
            [size],
        ).fetchall()

        for path, filename, needs_checksum in files:
            status = "NEEDS CHECKSUM" if needs_checksum else "has checksum"
            print(f"    {path}/{filename}: {status}")

    conn.close()


def test_with_empty_files():
    """Test the new query logic with empty file filtering."""
    print("\n=== Testing NEW query logic with empty file filtering ===")
    conn = create_test_database()

    # Add some empty files
    conn.executemany(
        """
    INSERT INTO files (path, filename, file_size, checksum, modification_datetime)
    VALUES (?, ?, ?, ?, ?)
    """,
        [
            ("/path9", "empty1.txt", 0, None, "2024-01-01 10:00:00"),
            ("/path10", "empty2.txt", 0, None, "2024-01-01 10:00:00"),
            ("/path11", "empty3.txt", 0, "xyz999", "2024-01-01 10:00:00"),
        ],
    )
    conn.commit()

    # New query with empty file filtering
    new_query_with_empty_filter = """
    SELECT file_size, COUNT(*) as file_count
    FROM files
    WHERE file_size > 0
    GROUP BY file_size
    HAVING COUNT(*) > 1 AND SUM(CASE WHEN checksum IS NULL THEN 1 ELSE 0 END) > 0
    ORDER BY file_size
    """

    results = conn.execute(new_query_with_empty_filter).fetchall()
    print(f"New query with empty file filtering found {len(results)} file sizes:")
    for size, count in results:
        print(f"  Size {size}: {count} files")

    conn.close()


if __name__ == "__main__":
    test_old_query()
    test_new_query()
    test_with_empty_files()

    print("\n=== SUMMARY ===")
    print("The old query only found file sizes where ALL files lacked checksums.")
    print("The new query correctly finds file sizes where:")
    print("1. There are multiple files with the same size")
    print("2. At least one of those files lacks a checksum")
    print("This ensures that newly added files get checksums calculated even if")
    print("other files of the same size already have checksums.")
