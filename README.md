# File Indexer

A high-performance file indexing tool using DuckDB with parallel processing and intelligent checksum optimization. Available in both Python and Go implementations.

[![codecov](https://codecov.io/gh/krzysbaranski/file-indexer/branch/main/graph/badge.svg)](https://codecov.io/gh/krzysbaranski/file-indexer)

## Features

- **Fast file indexing** with parallel processing
- **Intelligent checksum calculation** - only for potential duplicates
- **Two-phase indexing** - index metadata first, then calculate checksums selectively
- **Optimized database cleanup** - directory-first deletion detection with significant performance benefits
- **Configurable size limits** for checksum calculation
- **Duplicate file detection**
- **Flexible search capabilities**
- **Memory-efficient batch processing**
- **Automatic filtering** of symbolic links, device files, pipes, sockets, and other special files
- **Multiple implementations** - Python (full-featured) and Go (lightweight)

## Implementations

### Python Implementation (Full-Featured)
The Python implementation provides comprehensive file indexing with DuckDB backend, two-phase indexing, and advanced search capabilities.

### Go Implementation (Lightweight)
The Go implementation offers a simplified, fast file indexing tool with JSON storage and basic search functionality.

## Installation

### Python Implementation
```bash
poetry env 3.12
poetry install
```

### Go Implementation
```bash
cd file_indexer_go
go build
```

## Usage

### Python Implementation

#### Command Line Interface

#### Traditional Full Indexing
```bash
# Index a directory with all files getting checksums (slower but complete)
python -m file_indexer --scan /path/to/directory --db my_index.db

# Configuration options
python -m file_indexer --scan /path/to/directory \
    --db my_index.db \
    --max-checksum-size 100MB \
    --batch-size 500 \
    --max-workers 8
```

#### Two-Phase Indexing (Recommended)

**Option 1: All-in-one command**
```bash
# Complete two-phase indexing in one command
python -m file_indexer --two-phase /path/to/directory --db my_index.db
```

**Option 2: Separate processes (for operational flexibility)**
```bash
# Phase 1: Fast indexing without checksums (can be run separately)
python -m file_indexer --index-no-checksum /path/to/directory --db my_index.db

# Phase 2: Calculate checksums only for files with duplicate sizes (separate process)
python -m file_indexer --calculate-duplicates --db my_index.db
```

This approach allows you to:
- Run the fast indexing first to get immediate file metadata
- Run checksum calculation later as a background process
- Resume checksum calculation if interrupted
- Run checksum calculation on a different machine/schedule

#### Search and Analysis
```bash
# Find duplicate files
python -m file_indexer --find-duplicates --db my_index.db

# Search for files without checksums
python -m file_indexer --search-no-checksum --db my_index.db

# Search for files with checksums
python -m file_indexer --search-has-checksum --db my_index.db

# Search by filename pattern
python -m file_indexer --search-filename "*.py" --db my_index.db

# Search by path pattern
python -m file_indexer --search-path "/home/user/Documents/*" --db my_index.db

# Show database statistics
python -m file_indexer --stats --db my_index.db

# Database cleanup - remove records for deleted files
python -m file_indexer --cleanup --db my_index.db

# Clean up empty directories (directories with no files remaining)
python -m file_indexer --cleanup-empty-dirs --db my_index.db

# Dry run to see what would be cleaned up without making changes
python -m file_indexer --cleanup --dry-run --db my_index.db
```

### Go Implementation

#### Basic Commands
```bash
# Show help
./file_indexer_go

# Index a directory
./file_indexer_go -dir /path/to/directory

# Index with content (for searching within files)
./file_indexer_go -dir /path/to/directory -content

# Search for files
./file_indexer_go -search "query"

# List all indexed files
./file_indexer_go -list

# Show statistics
./file_indexer_go -stats

# Use DuckDB backend
./file_indexer_go -db -dir /path/to/directory

# Execute custom SQL query
./file_indexer_go -db -sql "SELECT * FROM files WHERE size > 1000000"
```

#### Command Line Options
- `-index string`: Path to the index file (default: "file_index.json")
- `-dir string`: Directory to index
- `-search string`: Search query
- `-list`: List all indexed files
- `-stats`: Show index statistics
- `-content`: Include file content in index
- `-max-size int`: Maximum file size to index in bytes (default: 1048576)
- `-db`: Use DuckDB database backend
- `-sql string`: Execute custom SQL query (database mode only)

### Programmatic Usage (Python)

```python
from file_indexer import FileIndexer

# Initialize with configuration
indexer = FileIndexer(
    db_path="my_index.db",
    max_workers=8,
    max_checksum_size=100 * 1024 * 1024,  # 100MB
    skip_empty_files=True,
    use_parallel_processing=True  # Set to False for sequential processing
)

# Traditional indexing
indexer.update_database("/path/to/directory")

# Two-phase indexing (recommended for large datasets)
indexer.two_phase_indexing("/path/to/directory")

# Or run phases separately
indexer.index_files_without_checksums("/path/to/directory")
indexer.calculate_checksums_for_duplicates()

# Search and analysis
indexer.find_duplicates()  # Prints duplicates to console
files_without_checksums = indexer.search_files(has_checksum=False)
stats = indexer.get_stats()

# Database cleanup - remove records for deleted files
cleanup_result = indexer.cleanup_deleted_files(dry_run=True)  # Dry run first
if cleanup_result['deleted_files'] > 0:
    indexer.cleanup_deleted_files(dry_run=False)  # Actually clean up

# Clean up empty directories
indexer.cleanup_empty_directories(dry_run=False)

indexer.close()
```

## Two-Phase Indexing Benefits

The two-phase approach provides significant performance benefits:

1. **Phase 1 (Fast)**: Index all file metadata without checksums
   - Captures file paths, sizes, modification times
   - Very fast - only filesystem metadata operations
   - Immediate searchability by name, size, date

2. **Phase 2 (Targeted)**: Calculate checksums only for potential duplicates
   - Only files with the same size get checksums
   - Respects the `skip_empty_files` setting (empty files are excluded from checksum calculation)
   - Dramatically reduces checksum calculations
   - Can be run separately or scheduled

### Performance Comparison

For a dataset with 100,000 files where only 5% are potential duplicates:
- **Traditional approach**: 100,000 checksum calculations
- **Two-phase approach**: ~5,000 checksum calculations (95% reduction)

## Database Cleanup

The indexer provides optimized cleanup functionality to remove database records for deleted files and directories:

### Cleanup Features

- **Directory-first optimization**: When entire directories are deleted, the cleanup process checks directories first and marks all files in deleted directories as removed without checking each file individually
- **Mixed deletion handling**: Efficiently handles scenarios where some directories are deleted entirely and some individual files are deleted
- **Dry run mode**: Preview what would be cleaned up without making changes
- **Batch processing**: Process cleanup operations in configurable batches for memory efficiency
- **Performance reporting**: Shows filesystem calls saved through optimization

### Cleanup Optimization Benefits

For your example scenario with `/tmp/f1/f2/` where `/tmp/f1` is deleted:

**Without optimization:**
- Check `/tmp/f1/f2/file1.txt` → No → Mark deleted
- Check `/tmp/f1/f2/file2.txt` → No → Mark deleted  
- Check `/tmp/f1/file3.txt` → No → Mark deleted
- **Total**: 3 individual file checks

**With optimization:**
- Check `/tmp/f1` directory → No → Mark all files under `/tmp/f1/*` as deleted
- **Total**: 1 directory check (saves 2 filesystem calls)

The optimization provides significant performance benefits when large directory trees are deleted, reducing filesystem I/O operations by up to 90% in scenarios with deep directory hierarchies.

## File Filtering

The indexer automatically filters out files that are not regular files to avoid errors and improve performance:

- **Symbolic links**: Skipped to avoid duplication and potential infinite loops
- **Device files**: Block and character devices (e.g., `/dev/sda`, `/dev/tty`)
- **Named pipes (FIFOs)**: Inter-process communication pipes
- **Sockets**: Network and Unix domain sockets
- **Other special files**: Any file that is not a regular file

This filtering happens automatically at multiple stages:
1. **During initial scanning**: Files are filtered when discovering files to index
2. **During checksum calculation**: Files are re-checked and filtered if the filesystem changed between indexing and checksum calculation (e.g., a regular file was replaced with a symlink)

The filtering cannot be disabled. The number of skipped files is reported in the statistics and can help identify unusual files in your directory structure.

## Configuration Options

### Python Implementation
- `--max-checksum-size`: Maximum file size for checksum calculation (default: 100MB)
- `--batch-size`: Files processed per batch (default: 1000)
- `--max-workers`: Parallel worker processes (default: CPU count + 4)
- `--sequential`: Force sequential processing instead of parallel (useful for restricted systems)
- `--no-skip-empty`: Calculate checksums for empty files (default: skip)
- `--no-recursive`: Don't scan subdirectories (default: recursive)

### Go Implementation
- `-max-size`: Maximum file size to index in bytes (default: 1MB)
- `-content`: Include file content in index for text search
- `-db`: Use DuckDB database backend instead of JSON storage

## Database Schema

### Python Implementation (DuckDB)
The tool uses DuckDB with the following schema:

```sql
CREATE TABLE files (
    path VARCHAR NOT NULL,
    filename VARCHAR NOT NULL,
    checksum VARCHAR,  -- Nullable for two-phase indexing
    modification_datetime TIMESTAMP NOT NULL,
    file_size BIGINT NOT NULL,
    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (path, filename)
);
```

### Go Implementation
The Go implementation supports both JSON file storage and DuckDB backend with similar schema.

## Examples

See `examples/example_usage.py` for comprehensive Python usage examples.

## Performance Tips

### Python Implementation
1. **Use two-phase indexing** for large datasets
2. **Adjust batch size** based on available memory
3. **Set appropriate checksum size limits** for your use case
4. **Use parallel processing** with `--max-workers`
5. **Run Phase 2 separately** for operational flexibility
6. **Use sequential processing** (`--sequential` or `--max-workers 1`) on systems with multiprocessing restrictions

### Go Implementation
1. **Use DuckDB backend** for large datasets and advanced queries
2. **Limit content indexing** to text files for better performance
3. **Set appropriate max-size limits** to avoid memory issues
4. **Use JSON storage** for simple use cases and portability

## Troubleshooting

### DuckDB Module Issues
If you encounter DuckDB module resolution errors, try:
```bash
# Clear Go module cache
go clean -modcache

# Re-download modules
go mod download

# Tidy up dependencies
go mod tidy
```

### Permission Denied Errors with Parallel Processing

If you encounter permission errors like `PermissionError: [Errno 13] Permission denied` when using parallel processing (common on NAS systems or containers), you have several options:

1. **Use the `--sequential` flag** to force sequential processing:
   ```bash
   file-indexer --sequential --calculate-duplicates --db my_index.db
   ```

2. **Set `--max-workers 1`** (automatically uses sequential processing):
   ```bash
   file-indexer --max-workers 1 --calculate-duplicates --db my_index.db
   ```

3. **Let it auto-fallback** - the tool will automatically fall back to sequential processing if parallel processing fails

## License

MIT License 
