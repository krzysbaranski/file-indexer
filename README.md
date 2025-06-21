# File Indexer

A high-performance file indexing tool using DuckDB with parallel processing and intelligent checksum optimization.

## Features

- **Fast file indexing** with parallel processing
- **Intelligent checksum calculation** - only for potential duplicates
- **Two-phase indexing** - index metadata first, then calculate checksums selectively
- **Configurable size limits** for checksum calculation
- **Duplicate file detection**
- **Flexible search capabilities**
- **Memory-efficient batch processing**

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Command Line Interface

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
```

### Programmatic Usage

```python
from file_indexer import FileIndexer

# Initialize with configuration
indexer = FileIndexer(
    db_path="my_index.db",
    max_workers=8,
    max_checksum_size=100 * 1024 * 1024,  # 100MB
    skip_empty_files=True
)

# Traditional indexing
indexer.update_database("/path/to/directory")

# Two-phase indexing (recommended for large datasets)
indexer.two_phase_indexing("/path/to/directory")

# Or run phases separately
indexer.index_files_without_checksums("/path/to/directory")
indexer.calculate_checksums_for_duplicates()

# Search and analysis
duplicates = indexer.find_duplicates()
files_without_checksums = indexer.search_files(has_checksum=False)
stats = indexer.get_stats()

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
   - Dramatically reduces checksum calculations
   - Can be run separately or scheduled

### Performance Comparison

For a dataset with 100,000 files where only 5% are potential duplicates:
- **Traditional approach**: 100,000 checksum calculations
- **Two-phase approach**: ~5,000 checksum calculations (95% reduction)

## Configuration Options

- `--max-checksum-size`: Maximum file size for checksum calculation (default: 100MB)
- `--batch-size`: Files processed per batch (default: 1000)
- `--max-workers`: Parallel worker processes (default: CPU count + 4)
- `--no-skip-empty`: Calculate checksums for empty files (default: skip)
- `--no-recursive`: Don't scan subdirectories (default: recursive)

## Database Schema

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

## Examples

See `examples/example_usage.py` for comprehensive usage examples.

## Performance Tips

1. **Use two-phase indexing** for large datasets
2. **Adjust batch size** based on available memory
3. **Set appropriate checksum size limits** for your use case
4. **Use parallel processing** with `--max-workers`
5. **Run Phase 2 separately** for operational flexibility

## License

MIT License 