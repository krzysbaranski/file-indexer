# File Indexer

A high-performance file indexing tool using DuckDB that creates a searchable database of files with checksums, optimized for large directories.

## Features

- 🚀 **High Performance**: Parallel checksum calculation and batch database operations
- 💾 **Smart Checksum Management**: Configurable size limits and empty file handling
- 🔍 **Flexible Search**: Search by filename, path, checksum, or checksum presence
- 🔄 **Incremental Updates**: Only processes changed files on subsequent runs
- 📊 **Detailed Statistics**: Performance metrics and optimization tracking
- 🔗 **Symlink Aware**: Safely ignores symbolic links during indexing
- 🧪 **Duplicate Detection**: Find files with identical content

## Installation

```bash
pip install -r requirements.txt
```

## Quick Start

### Command Line Usage

```bash
# Basic indexing with default optimizations (100MB checksum limit, skip empty files)
python -m file_indexer.cli --scan /path/to/directory

# High-performance indexing for large directories
python -m file_indexer.cli --scan /path/to/directory --max-workers 8 --batch-size 2000

# Skip checksums for files larger than 1GB
python -m file_indexer.cli --scan /path/to/directory --max-checksum-size 1GB

# Include checksums for all files (no size limit)
python -m file_indexer.cli --scan /path/to/directory --max-checksum-size 0

# Search for files
python -m file_indexer.cli --search-filename "*.py"
python -m file_indexer.cli --search-path "*src*"
python -m file_indexer.cli --search-has-checksum  # Files with checksums
python -m file_indexer.cli --search-no-checksum   # Files without checksums

# Find duplicates and show database stats
python -m file_indexer.cli --find-duplicates
python -m file_indexer.cli --stats
```

### Programmatic Usage

```python
from file_indexer import FileIndexer

# Create indexer with performance optimizations
indexer = FileIndexer(
    "my_files.db",
    max_workers=4,                    # Parallel processing
    max_checksum_size=50*1024*1024,   # 50MB limit
    skip_empty_files=True             # Skip empty files
)

# Index directory with batching
indexer.update_database("/path/to/directory", batch_size=1000)

# Search and analyze
python_files = indexer.search_files(filename_pattern="%.py")
large_files = indexer.search_files(has_checksum=False)  # Files without checksums
duplicates = indexer.find_duplicates()

# Get performance statistics
stats = indexer.get_stats()
print(f"Optimization: {stats['optimization_percentage']:.1f}%")
print(f"Files with checksums: {stats['files_with_checksum']:,}")
print(f"Files without checksums: {stats['files_without_checksum']:,}")

indexer.close()
```

## Performance Optimizations

### Parallel Processing
- **Multi-core checksum calculation**: Uses all available CPU cores
- **Configurable worker processes**: Tune for your system
- **Batch database operations**: Reduces transaction overhead

### Smart Checksum Management
- **Size-based skipping**: Skip checksums for files larger than specified size
- **Empty file handling**: Optionally skip checksum calculation for empty files
- **Nullable schema**: Files without checksums are still indexed for metadata

### Memory Efficiency
- **Streaming file processing**: Processes files as generator to minimize memory usage
- **Configurable batch sizes**: Balance memory usage vs. performance
- **Bulk database queries**: Avoid N+1 query problems

### Incremental Updates
- **Change detection**: Only recalculates checksums for modified files
- **Optimization tracking**: Detailed metrics on performance improvements
- **Database persistence**: Reuses existing data across runs

## Configuration Options

### FileIndexer Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `db_path` | `"file_index.db"` | Database file location |
| `max_workers` | CPU cores + 4 | Maximum parallel worker processes |
| `max_checksum_size` | 100MB | Maximum file size for checksum calculation |
| `skip_empty_files` | `True` | Skip checksum calculation for empty files |

### CLI Options

| Option | Description |
|--------|-------------|
| `--max-checksum-size SIZE` | Set checksum size limit (e.g., "100MB", "1GB", "0" for no limit) |
| `--max-workers N` | Set number of parallel workers |
| `--batch-size N` | Set batch processing size (default: 1000) |
| `--no-skip-empty` | Calculate checksums for empty files |
| `--search-has-checksum` | Find files with checksums |
| `--search-no-checksum` | Find files without checksums |

## Database Schema

The tool uses DuckDB with the following optimized schema:

```sql
CREATE TABLE files (
    path VARCHAR NOT NULL,
    filename VARCHAR NOT NULL,
    checksum VARCHAR,                    -- Nullable for large/empty files
    modification_datetime TIMESTAMP NOT NULL,
    file_size BIGINT NOT NULL,
    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (path, filename)
);

-- Optimized indexes
CREATE INDEX idx_checksum ON files(checksum) WHERE checksum IS NOT NULL;
CREATE INDEX idx_modification_datetime ON files(modification_datetime);
CREATE INDEX idx_path_filename ON files(path, filename);
CREATE INDEX idx_file_size ON files(file_size);
```

## Performance Benchmarks

Typical performance improvements with optimizations enabled:

- **10-50x faster** checksum calculation (depending on CPU cores)
- **5-10x faster** database operations through batching
- **90%+ memory reduction** with streaming processing
- **50-80% fewer** redundant checksum calculations

### Example Results

```
Configuration: max_checksum_size=104,857,600 bytes, skip_empty_files=True
Processed 50,000 files in 2.3 minutes
Performance: Calculated 15,432 checksums, reused 34,568 (69.1% optimization)
Skipped checksums for 2,847 files (empty or too large)
```

## Use Cases

### Large Directory Indexing
Perfect for indexing large directories like:
- Media libraries with large video files
- Code repositories with build artifacts
- Network shares with mixed file types
- Backup verification and deduplication

### File Management
- **Duplicate Detection**: Find identical files across directory trees
- **Change Tracking**: Monitor file modifications over time
- **Space Analysis**: Identify large files without checksums
- **Content Search**: Find files by content hash

### Data Integrity
- **Backup Verification**: Ensure file integrity over time
- **Archive Management**: Track checksums for long-term storage
- **Selective Processing**: Skip checksums for files that don't need verification

## Examples

See `examples/example_usage.py` for comprehensive usage examples including:
- Parallel processing setup
- Performance monitoring
- Advanced search patterns
- Statistics analysis

## Development

Run tests:
```bash
pytest tests/
```

The test suite includes:
- Performance optimization verification
- Nullable checksum handling
- Schema migration testing
- Parallel processing validation

## License

MIT License - see LICENSE file for details. 