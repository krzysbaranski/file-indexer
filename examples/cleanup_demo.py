#!/usr/bin/env python3
"""
Demo script showing the cleanup optimization benefits.
Creates a directory structure, deletes some directories, and shows the optimization.
"""

import tempfile
import shutil
from pathlib import Path
from file_indexer import FileIndexer


def create_test_structure():
    """Create a test directory structure with nested directories and files."""
    base_dir = Path(tempfile.mkdtemp(prefix="cleanup_demo_"))
    print(f"Created test directory: {base_dir}")
    
    # Create nested directory structure
    structure = {
        "dir1": ["file1.txt", "file2.txt"],
        "dir2": ["file3.txt", "file4.txt", "file5.txt"],
        "dir3/subdir1": ["file6.txt", "file7.txt"],
        "dir3/subdir2": ["file8.txt"],
        "dir4": ["file9.txt"],
        "": ["root_file.txt"]  # Root level file
    }
    
    for dir_path, files in structure.items():
        if dir_path:
            full_dir = base_dir / dir_path
            full_dir.mkdir(parents=True, exist_ok=True)
        else:
            full_dir = base_dir
            
        for filename in files:
            file_path = full_dir / filename
            file_path.write_text(f"Content of {filename}")
    
    return base_dir


def main():
    """Demonstrate the cleanup optimization."""
    print("=== File Indexer Cleanup Optimization Demo ===\n")
    
    # Create test structure
    test_dir = create_test_structure()
    
    try:
        # Initialize indexer
        indexer = FileIndexer("cleanup_demo.db")
        
        try:
            # Index all files
            print("1. Indexing all files...")
            indexer.update_database(str(test_dir), recursive=True)
            
            initial_stats = indexer.get_stats()
            print(f"   Indexed {initial_stats['total_files']} files")
            
            # Show directory structure
            print("\n2. Directory structure:")
            import os
            for root, dirs, files in os.walk(test_dir):
                root_path = Path(root)
                level = len(root_path.relative_to(test_dir).parts)
                indent = "  " * level
                if level == 0:
                    print(f"{root_path.name}/")
                else:
                    print(f"{indent}{root_path.name}/")
                for file in files:
                    print(f"{indent}  {file}")
            
            # Delete some entire directories
            print("\n3. Deleting directories...")
            dirs_to_delete = [
                test_dir / "dir1",
                test_dir / "dir3" / "subdir1",
            ]
            
            for dir_path in dirs_to_delete:
                if dir_path.exists():
                    print(f"   Deleting: {dir_path.relative_to(test_dir)}")
                    shutil.rmtree(dir_path)
            
            # Delete an individual file
            individual_file = test_dir / "dir2" / "file3.txt"
            if individual_file.exists():
                print(f"   Deleting individual file: {individual_file.relative_to(test_dir)}")
                individual_file.unlink()
            
            # Run cleanup with the optimized approach
            print("\n4. Running optimized cleanup...")
            cleanup_result = indexer.cleanup_deleted_files(dry_run=False)
            
            # Show results
            print("\n=== Cleanup Results ===")
            print(f"Total files checked: {cleanup_result['total_checked']:,}")
            print(f"Deleted files found: {cleanup_result['deleted_files']:,}")
            print(f"  - Deleted via directory check: {cleanup_result['files_deleted_by_directory']:,}")
            print(f"  - Deleted via individual check: {cleanup_result['files_deleted_individually']:,}")
            print(f"Deleted directories: {cleanup_result['deleted_directories']:,}")
            
            if cleanup_result.get('filesystem_calls_saved', 0) > 0:
                print(f"Filesystem calls saved: {cleanup_result['filesystem_calls_saved']:,}")
            
            # Show final stats
            final_stats = indexer.get_stats()
            print(f"\nFinal database: {final_stats['total_files']} files remaining")
            
            # Demonstrate the optimization benefit
            print("\n=== Optimization Benefits ===")
            print("Without optimization (old approach):")
            print(f"  - Would check each file individually: {initial_stats['total_files']} checks")
            print("\nWith optimization (new approach):")
            print(f"  - Directory checks: {cleanup_result['deleted_directories']} (found {cleanup_result['files_deleted_by_directory']} deleted files)")
            print(f"  - Individual file checks: {cleanup_result['files_deleted_individually']} (only for files in existing directories)")
            print(f"  - Total filesystem operations saved: {cleanup_result.get('filesystem_calls_saved', 0)}")
            
            if cleanup_result.get('filesystem_calls_saved', 0) > 0:
                efficiency = (cleanup_result['filesystem_calls_saved'] / initial_stats['total_files']) * 100
                print(f"  - Efficiency improvement: {efficiency:.1f}%")
            
        finally:
            indexer.close()
    
    finally:
        # Clean up
        shutil.rmtree(test_dir, ignore_errors=True)
        Path("cleanup_demo.db").unlink(missing_ok=True)
        print(f"\nCleaned up test directory and database")


if __name__ == "__main__":
    main() 