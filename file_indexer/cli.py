"""
Command-line interface for the File Indexer.
"""

import argparse

from .indexer import FileIndexer
from .utils import format_size


def parse_size(size_str: str) -> int:
    """Parse size string like '100MB' to bytes."""
    if not size_str:
        return 0

    size_str = size_str.upper()
    multipliers = {
        "B": 1,
        "K": 1024,
        "KB": 1024,
        "M": 1024**2,
        "MB": 1024**2,
        "G": 1024**3,
        "GB": 1024**3,
        "T": 1024**4,
        "TB": 1024**4,
    }

    # Extract number and unit
    import re

    match = re.match(r"^(\d+(?:\.\d+)?)\s*([A-Z]*)?$", size_str)
    if not match:
        raise ValueError(f"Invalid size format: {size_str}")

    number = float(match.group(1))
    unit = match.group(2) or "B"

    if unit not in multipliers:
        raise ValueError(f"Unknown size unit: {unit}")

    return int(number * multipliers[unit])


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="File Indexer using DuckDB")
    parser.add_argument("--db", default="file_index.db", help="Database file path")
    parser.add_argument("--scan", help="Directory path to scan and index")
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Don't scan subdirectories recursively",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Number of files to process in each batch (default: 1000)",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        help="Maximum number of worker processes for parallel operations",
    )
    parser.add_argument(
        "--max-checksum-size",
        type=str,
        default="100MB",
        help="Maximum file size to calculate checksums for (e.g., '100MB', '1GB', '0' for no limit)",
    )
    parser.add_argument(
        "--no-skip-empty",
        action="store_true",
        help="Don't skip checksum calculation for empty files",
    )
    parser.add_argument(
        "--sequential",
        action="store_true",
        help="Force sequential processing instead of parallel (useful for systems with restricted multiprocessing)",
    )
    parser.add_argument(
        "--two-phase",
        help="Perform two-phase indexing: first index without checksums, then calculate checksums for files with duplicate sizes",
    )
    parser.add_argument(
        "--index-no-checksum",
        help="Phase 1 only: Index files without calculating checksums (fast)",
    )
    parser.add_argument(
        "--calculate-duplicates",
        action="store_true",
        help="Phase 2 only: Calculate checksums for files with duplicate sizes",
    )
    parser.add_argument(
        "--search-filename", help="Search for files by filename pattern"
    )
    parser.add_argument("--search-path", help="Search for files by path pattern")
    parser.add_argument("--search-checksum", help="Search for files by exact checksum")
    parser.add_argument(
        "--search-no-checksum",
        action="store_true",
        help="Search for files without checksums",
    )
    parser.add_argument(
        "--search-has-checksum",
        action="store_true",
        help="Search for files with checksums",
    )
    parser.add_argument(
        "--find-duplicates", action="store_true", help="Find duplicate files"
    )
    parser.add_argument("--stats", action="store_true", help="Show database statistics")
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Clean up database by removing records for deleted files",
    )
    parser.add_argument(
        "--cleanup-empty-dirs",
        action="store_true",
        help="Remove database records for empty directories",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=10000,
        help="Number of records to process per page in cleanup operations (default: 10000)",
    )

    args = parser.parse_args()

    # Parse configuration
    max_checksum_size = (
        parse_size(args.max_checksum_size) if args.max_checksum_size != "0" else 0
    )
    skip_empty_files = not args.no_skip_empty

    indexer = FileIndexer(
        args.db,
        max_workers=args.max_workers,
        max_checksum_size=max_checksum_size,
        skip_empty_files=skip_empty_files,
        use_parallel_processing=not args.sequential,
    )

    try:
        if args.scan:
            indexer.update_database(
                args.scan, not args.no_recursive, batch_size=args.batch_size
            )
        elif args.two_phase:
            indexer.two_phase_indexing(
                args.two_phase, not args.no_recursive, batch_size=args.batch_size
            )
        elif args.index_no_checksum:
            indexer.index_files_without_checksums(
                args.index_no_checksum,
                not args.no_recursive,
                batch_size=args.batch_size,
            )
        elif args.calculate_duplicates:
            indexer.calculate_checksums_for_duplicates(batch_size=args.batch_size // 2)
        elif any(
            [
                args.search_filename,
                args.search_path,
                args.search_checksum,
                args.search_no_checksum,
                args.search_has_checksum,
            ]
        ):
            has_checksum = None
            if args.search_no_checksum:
                has_checksum = False
            elif args.search_has_checksum:
                has_checksum = True

            results = indexer.search_files(
                args.search_filename,
                args.search_checksum,
                args.search_path,
                has_checksum=has_checksum,
            )
            if results:
                print(f"Found {len(results)} matching files:")
                for result in results:
                    checksum_display = (
                        result["checksum"][:16] + "..."
                        if result["checksum"]
                        else "None"
                    )
                    size_display = format_size(result["file_size"])
                    print(
                        f"  {result['path']}/{result['filename']} (checksum: {checksum_display}, size: {size_display})"
                    )
            else:
                print("No matching files found.")
        elif args.find_duplicates:
            indexer.find_duplicates()
        elif args.stats:
            stats = indexer.get_stats()
            print("Database Statistics:")
            print(f"  Total files: {stats['total_files']:,}")
            print(f"  Total size: {format_size(stats['total_size'])}")
            print(f"  Files with checksums: {stats['files_with_checksum']:,}")
            print(f"  Files without checksums: {stats['files_without_checksum']:,}")
            print(f"  Unique checksums: {stats['unique_checksums']:,}")
            print(f"  Duplicate files: {stats['duplicate_files']:,}")
            print(f"  Last indexed: {stats['last_indexed']}")

            # Performance stats if available
            if stats["checksum_calculations"] > 0 or stats["checksum_reuses"] > 0:
                print("\nPerformance Statistics:")
                print(f"  Checksum calculations: {stats['checksum_calculations']:,}")
                print(f"  Checksum reuses: {stats['checksum_reuses']:,}")
                print(f"  Skipped checksums: {stats['skipped_checksums']:,}")
                print(f"  Optimization: {stats['optimization_percentage']:.1f}%")

            # Cleanup stats if available
            if stats.get("deleted_files", 0) > 0:
                print(f"  Deleted files cleaned: {stats['deleted_files']:,}")
        elif args.cleanup:
            cleanup_result = indexer.cleanup_deleted_files(
                batch_size=args.batch_size, page_size=args.page_size
            )
            print("\nCleanup Summary:")
            print(f"  Files checked: {cleanup_result['total_checked']:,}")
            print(f"  Files deleted from database: {cleanup_result['deleted_files']:,}")
            print(f"  Directories deleted: {cleanup_result['deleted_directories']:,}")
            if cleanup_result["permission_errors"] > 0:
                print(f"  Permission errors: {cleanup_result['permission_errors']:,}")
        elif args.cleanup_empty_dirs:
            cleanup_result = indexer.cleanup_empty_directories(page_size=args.page_size)
            print("\nEmpty Directory Cleanup Summary:")
            print(f"  Directories checked: {cleanup_result['total_checked']:,}")
            print(
                f"  Directories deleted from database: {cleanup_result['deleted_directories']:,}"
            )
            if cleanup_result["permission_errors"] > 0:
                print(f"  Permission errors: {cleanup_result['permission_errors']:,}")
        else:
            parser.print_help()

    finally:
        indexer.close()


if __name__ == "__main__":
    main()
