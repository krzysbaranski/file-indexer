#!/usr/bin/env python3
"""
Example usage of the FileIndexer class.
This demonstrates how to use the file indexer programmatically with the new optimizations.
"""

from pathlib import Path

from file_indexer import FileIndexer


def format_size(size_bytes: int) -> str:
    """Format file size in human readable format."""
    if size_bytes == 0:
        return "0 B"

    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(size_bytes)
    unit_index = 0

    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    return f"{size:.1f} {units[unit_index]}"


def main():
    # Initialize the file indexer with optimizations
    # Skip checksums for files larger than 50MB and empty files
    indexer = FileIndexer(
        "example_file_index.db",
        max_workers=4,  # Use 4 parallel workers
        max_checksum_size=50 * 1024 * 1024,  # 50MB limit
        skip_empty_files=True,
    )

    print("=== Optimized File Indexer Example ===\n")

    try:
        # Example 1: Index the current directory with batching
        current_dir = Path.cwd()
        print(f"1. Indexing current directory: {current_dir}")
        print("   Using parallel processing and checksum optimization...")
        indexer.update_database(str(current_dir), recursive=True, batch_size=500)
        print()

        # Example 2: Show enhanced database statistics
        print("2. Enhanced Database Statistics:")
        stats = indexer.get_stats()
        print(f"   Total files: {stats['total_files']:,}")
        print(f"   Total size: {format_size(stats['total_size'])}")
        print(f"   Files with checksums: {stats['files_with_checksum']:,}")
        print(f"   Files without checksums: {stats['files_without_checksum']:,}")
        print(f"   Unique checksums: {stats['unique_checksums']:,}")
        print(f"   Duplicate files: {stats['duplicate_files']:,}")
        print(f"   Last indexed: {stats['last_indexed']}")

        if stats["checksum_calculations"] > 0 or stats["checksum_reuses"] > 0:
            print(f"\n   Performance Statistics:")
            print(f"   Checksum calculations: {stats['checksum_calculations']:,}")
            print(f"   Checksum reuses: {stats['checksum_reuses']:,}")
            print(f"   Skipped checksums: {stats['skipped_checksums']:,}")
            print(f"   Optimization: {stats['optimization_percentage']:.1f}%")
        print()

        # Example 3: Search for files with and without checksums
        print("3. Searching for files with checksums:")
        files_with_checksums = indexer.search_files(has_checksum=True)
        for file_info in files_with_checksums[:3]:  # Show first 3
            checksum_short = (
                file_info["checksum"][:16] + "..." if file_info["checksum"] else "None"
            )
            size_str = format_size(file_info["file_size"])
            print(
                f"   {file_info['path']}/{file_info['filename']} ({checksum_short}, {size_str})"
            )
        if len(files_with_checksums) > 3:
            print(
                f"   ... and {len(files_with_checksums) - 3} more files with checksums"
            )
        print()

        print("4. Searching for files without checksums:")
        files_without_checksums = indexer.search_files(has_checksum=False)
        for file_info in files_without_checksums[:3]:  # Show first 3
            size_str = format_size(file_info["file_size"])
            print(
                f"   {file_info['path']}/{file_info['filename']} (no checksum, {size_str})"
            )
        if len(files_without_checksums) > 3:
            print(
                f"   ... and {len(files_without_checksums) - 3} more files without checksums"
            )
        print()

        # Example 5: Find duplicate files (only among files with checksums)
        print("5. Looking for duplicate files:")
        duplicates = indexer.find_duplicates()
        if duplicates:
            print(f"   Found {len(duplicates)} duplicate files:")
            current_checksum = None
            for count, dup in enumerate(duplicates):
                if count >= 6:  # Limit output
                    print("   ... (truncated)")
                    break
                if dup["checksum"] != current_checksum:
                    current_checksum = dup["checksum"]
                    print(f"   Checksum {current_checksum[:16]}...:")
                size_str = format_size(dup["file_size"])
                print(f"     {dup['path']}/{dup['filename']} ({size_str})")
        else:
            print("   No duplicate files found.")
        print()

        # Example 6: Search by file extension and size
        print("6. Searching for Python files:")
        python_files = indexer.search_files(filename_pattern="%.py")
        if python_files:
            for file_info in python_files[:3]:  # Show first 3 results
                size_str = format_size(file_info["file_size"])
                checksum_str = (
                    "with checksum" if file_info["checksum"] else "no checksum"
                )
                print(
                    f"   {file_info['path']}/{file_info['filename']} ({size_str}, {checksum_str})"
                )
            if len(python_files) > 3:
                print(f"   ... and {len(python_files) - 3} more Python files")
        else:
            print("   No .py files found.")

    except Exception as e:
        print(f"Error: {e}")

    finally:
        # Always close the database connection
        indexer.close()
        print("\nExample completed!")


if __name__ == "__main__":
    main()
