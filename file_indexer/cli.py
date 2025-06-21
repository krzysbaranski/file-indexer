"""
Command-line interface for the File Indexer.
"""

import argparse

from .indexer import FileIndexer


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
        "--search-filename", help="Search for files by filename pattern"
    )
    parser.add_argument("--search-path", help="Search for files by path pattern")
    parser.add_argument("--search-checksum", help="Search for files by exact checksum")
    parser.add_argument(
        "--find-duplicates", action="store_true", help="Find duplicate files"
    )
    parser.add_argument("--stats", action="store_true", help="Show database statistics")

    args = parser.parse_args()

    indexer = FileIndexer(args.db)

    try:
        if args.scan:
            indexer.update_database(args.scan, not args.no_recursive)
        elif args.search_filename or args.search_path or args.search_checksum:
            results = indexer.search_files(
                args.search_filename, args.search_checksum, args.search_path
            )
            if results:
                print(f"Found {len(results)} matching files:")
                for result in results:
                    print(
                        f"  {result['path']}/{result['filename']} (checksum: {result['checksum'][:16]}...)"
                    )
            else:
                print("No matching files found.")
        elif args.find_duplicates:
            duplicates = indexer.find_duplicates()
            if duplicates:
                print(f"Found {len(duplicates)} duplicate files:")
                current_checksum = None
                for dup in duplicates:
                    if dup["checksum"] != current_checksum:
                        current_checksum = dup["checksum"]
                        print(f"\nChecksum {current_checksum}:")
                    print(f"  {dup['path']}/{dup['filename']}")
            else:
                print("No duplicate files found.")
        elif args.stats:
            stats = indexer.get_stats()
            print("Database Statistics:")
            print(f"  Total files: {stats['total_files']:,}")
            print(
                f"  Total size: {stats['total_size']:,} bytes ({stats['total_size'] / 1024 / 1024:.2f} MB)"
            )
            print(f"  Unique files: {stats['unique_checksums']:,}")
            print(f"  Duplicate files: {stats['duplicate_files']:,}")
            print(f"  Last indexed: {stats['last_indexed']}")
        else:
            parser.print_help()

    finally:
        indexer.close()


if __name__ == "__main__":
    main()
