#!/usr/bin/env python3
"""
Example usage of the File Indexer with various features.
"""

from file_indexer import FileIndexer


def main():
    """Demonstrate various file indexer features."""
    # Initialize indexer
    indexer = FileIndexer(
        db_path="example_index.db",
        max_workers=4,
        max_checksum_size=50 * 1024 * 1024,  # 50MB
        skip_empty_files=True,
    )

    try:
        # Example 1: Traditional full indexing (slower but complete)
        print("=== Example 1: Traditional Full Indexing ===")
        indexer.update_database("/path/to/directory", recursive=True)

        # Example 2: Two-phase indexing (recommended for large datasets)
        print("\n=== Example 2: Two-Phase Indexing ===")
        indexer2 = FileIndexer("two_phase_index.db")

        # This is much faster as it's the complete process
        indexer2.two_phase_indexing("/path/to/directory", recursive=True)
        indexer2.close()

        # Example 3: Manual two-phase process (for separate CLI processes)
        print("\n=== Example 3: Manual Two-Phase Process ===")
        indexer3 = FileIndexer("manual_index.db")

        # Phase 1: Fast indexing without checksums
        print("Phase 1: Indexing files without checksums...")
        indexer3.index_files_without_checksums("/path/to/directory", recursive=True)

        # Phase 2: Calculate checksums only for potential duplicates
        print("Phase 2: Calculating checksums for files with duplicate sizes...")
        indexer3.calculate_checksums_for_duplicates()

        indexer3.close()

        # Example 4: Search operations
        print("\n=== Example 4: Search Operations ===")

        # Find files without checksums
        no_checksum_files = indexer.search_files(has_checksum=False)
        print(f"Files without checksums: {len(no_checksum_files)}")

        # Find files with checksums
        with_checksum_files = indexer.search_files(has_checksum=True)
        print(f"Files with checksums: {len(with_checksum_files)}")

        # Find duplicates
        duplicates = indexer.find_duplicates()
        print(f"Duplicate files found: {len(duplicates)}")

        # Show statistics
        stats = indexer.get_stats()
        print("\nDatabase Statistics:")
        print(f"  Total files: {stats['total_files']:,}")
        print(f"  Files with checksums: {stats['files_with_checksum']:,}")
        print(f"  Files without checksums: {stats['files_without_checksum']:,}")
        print(f"  Duplicate files: {stats['duplicate_files']:,}")

        # Example 5: Database cleanup
        print("\n=== Example 5: Database Cleanup ===")
        
        # Check for deleted files (dry run first)
        print("Checking for deleted files (dry run)...")
        cleanup_result = indexer.cleanup_deleted_files(dry_run=True)
        print(f"Files checked: {cleanup_result['total_checked']:,}")
        print(f"Deleted files found: {cleanup_result['deleted_files']:,}")
        
        # Actually clean up deleted files if any found
        if cleanup_result['deleted_files'] > 0:
            print("\nCleaning up deleted files...")
            cleanup_result = indexer.cleanup_deleted_files(dry_run=False)
            print(f"Cleaned up {cleanup_result['deleted_files']:,} deleted files")
        
        # Check for empty directories
        print("\nChecking for empty directories...")
        empty_dirs_result = indexer.cleanup_empty_directories(dry_run=True)
        print(f"Empty directories found: {empty_dirs_result['empty_directories']:,}")
        
        # Clean up empty directories if any found
        if empty_dirs_result['empty_directories'] > 0:
            print("Cleaning up empty directories...")
            empty_dirs_result = indexer.cleanup_empty_directories(dry_run=False)
            print(f"Cleaned up {empty_dirs_result['files_in_empty_dirs']:,} files from {empty_dirs_result['empty_directories']:,} empty directories")

    except Exception as e:
        print(f"Error: {e}")

    finally:
        indexer.close()
        print("\nExample completed!")


if __name__ == "__main__":
    main()
