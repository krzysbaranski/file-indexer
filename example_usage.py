#!/usr/bin/env python3
"""
Example usage of the FileIndexer class.
This demonstrates how to use the file indexer programmatically.
"""

from file_indexer import FileIndexer
import os


def main():
    # Initialize the file indexer with a database file
    indexer = FileIndexer("example_file_index.db")
    
    print("=== File Indexer Example ===\n")
    
    try:
        # Example 1: Index the current directory
        current_dir = os.getcwd()
        print(f"1. Indexing current directory: {current_dir}")
        indexer.update_database(current_dir, recursive=True)
        print()
        
        # Example 2: Show database statistics
        print("2. Database Statistics:")
        stats = indexer.get_stats()
        print(f"   Total files: {stats['total_files']:,}")
        print(f"   Total size: {stats['total_size']:,} bytes ({stats['total_size']/1024/1024:.2f} MB)")
        print(f"   Unique files: {stats['unique_checksums']:,}")
        print(f"   Duplicate files: {stats['duplicate_files']:,}")
        print(f"   Last indexed: {stats['last_indexed']}")
        print()
        
        # Example 3: Search for Python files
        print("3. Searching for Python files:")
        python_files = indexer.search_files(filename_pattern="%.py")
        for file_info in python_files[:5]:  # Show first 5 results
            print(f"   {file_info['path']}/{file_info['filename']}")
        if len(python_files) > 5:
            print(f"   ... and {len(python_files) - 5} more Python files")
        print()
        
        # Example 4: Find duplicate files
        print("4. Looking for duplicate files:")
        duplicates = indexer.find_duplicates()
        if duplicates:
            print(f"   Found {len(duplicates)} duplicate files:")
            current_checksum = None
            count = 0
            for dup in duplicates:
                if count >= 10:  # Limit output
                    print("   ... (truncated)")
                    break
                if dup['checksum'] != current_checksum:
                    current_checksum = dup['checksum']
                    print(f"   Checksum {current_checksum[:16]}...:")
                print(f"     {dup['path']}/{dup['filename']}")
                count += 1
        else:
            print("   No duplicate files found.")
        print()
        
        # Example 5: Search by file extension
        print("5. Searching for text files:")
        text_files = indexer.search_files(filename_pattern="%.txt")
        if text_files:
            for file_info in text_files[:3]:  # Show first 3 results
                print(f"   {file_info['path']}/{file_info['filename']} (Size: {file_info['file_size']} bytes)")
        else:
            print("   No .txt files found.")
        
    except Exception as e:
        print(f"Error: {e}")
    
    finally:
        # Always close the database connection
        indexer.close()
        print("\nExample completed!")


if __name__ == "__main__":
    main() 