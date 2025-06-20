# File Indexer using DuckDB

A Python-based file indexing system that creates and maintains a DuckDB database of files with their metadata, including checksums, modification dates, and file sizes.

## Features

- **Comprehensive File Metadata**: Tracks file path, filename, SHA256 checksum, modification datetime, and file size
- **Efficient Storage**: Uses DuckDB for high-performance analytical queries
- **Duplicate Detection**: Find files with identical content using checksum comparison
- **Flexible Search**: Search files by name patterns, paths, or checksums
- **Incremental Updates**: Only recalculates checksums for modified files
- **Command Line Interface**: Easy-to-use CLI for common operations
- **Programmatic API**: Full Python API for custom integrations

## Installation

1. Install the required dependency:
```bash
pip install -r requirements.txt
```

## Database Schema

The file indexer creates a table with the following schema:

```sql
CREATE TABLE files (
    path VARCHAR NOT NULL,
    filename VARCHAR NOT NULL,
    checksum VARCHAR NOT NULL,
    modification_datetime TIMESTAMP NOT NULL,
    file_size BIGINT NOT NULL,
    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (path, filename)
);
```

## Usage

### Command Line Interface

#### Index a Directory
```bash
# Index current directory recursively
python file_indexer.py --scan .

# Index a specific directory
python file_indexer.py --scan /path/to/directory

# Index without recursion (current directory only)
python file_indexer.py --scan /path/to/directory --no-recursive

# Use custom database file
python file_indexer.py --db custom_index.db --scan /path/to/directory
```

#### Search Files
```bash
# Search by filename pattern
python file_indexer.py --search-filename "*.py"

# Search by path pattern
python file_indexer.py --search-path "*Documents*"

# Search by exact checksum
python file_indexer.py --search-checksum abc123def456...

# Combine multiple search criteria
python file_indexer.py --search-filename "*.txt" --search-path "*backup*"
```

#### Find Duplicates
```bash
# Find all duplicate files
python file_indexer.py --find-duplicates
```

#### Database Statistics
```bash
# Show database statistics
python file_indexer.py --stats
```

### Programmatic Usage

```python
from file_indexer import FileIndexer

# Initialize indexer
indexer = FileIndexer("my_index.db")

try:
    # Index a directory
    indexer.update_database("/path/to/directory", recursive=True)
    
    # Search for files
    python_files = indexer.search_files(filename_pattern="%.py")
    
    # Find duplicates
    duplicates = indexer.find_duplicates()
    
    # Get statistics
    stats = indexer.get_stats()
    print(f"Total files: {stats['total_files']}")
    
finally:
    indexer.close()
```

## API Reference

### FileIndexer Class

#### Constructor
```python
FileIndexer(db_path: str = "file_index.db")
```

#### Methods

##### `update_database(directory_path: str, recursive: bool = True)`
Scans a directory and updates the database with file information.

##### `search_files(filename_pattern=None, checksum=None, path_pattern=None)`
Search for files matching the given criteria. Returns a list of dictionaries with file information.

##### `find_duplicates()`
Find files with identical checksums. Returns a list of dictionaries with duplicate file information.

##### `get_stats()`
Get database statistics including total files, size, and duplicate counts.

##### `close()`
Close the database connection.

## Examples

### Basic Usage
```python
# Run the example script
python example_usage.py
```

### Advanced Queries
```python
from file_indexer import FileIndexer

indexer = FileIndexer()

# Find large files (>10MB)
large_files = indexer.conn.execute("""
    SELECT path, filename, file_size 
    FROM files 
    WHERE file_size > 10485760 
    ORDER BY file_size DESC
""").fetchall()

# Find recently modified files (last 7 days)
recent_files = indexer.conn.execute("""
    SELECT path, filename, modification_datetime 
    FROM files 
    WHERE modification_datetime > datetime('now', '-7 days')
    ORDER BY modification_datetime DESC
""").fetchall()

indexer.close()
```

## Performance Considerations

- **Checksum Calculation**: SHA256 checksums are calculated for all files. For large files or many files, this can be time-consuming.
- **Incremental Updates**: The system only recalculates checksums for files that have been modified since the last scan.
- **Database Indexes**: The system creates indexes on frequently queried columns for better performance.
- **Memory Usage**: Files are read in 8KB chunks to minimize memory usage for large files.

## File Handling

- **Permissions**: Files that can't be read due to permissions are skipped with a warning.
- **Symbolic Links**: The system follows symbolic links and indexes the target files.
- **Hidden Files**: Hidden files (starting with '.') are included in the index.
- **Binary Files**: All file types are supported, including binary files.

## Database Files

- **Default Location**: `file_index.db` in the current directory
- **Portability**: DuckDB files are portable across platforms
- **Size**: Database size depends on the number of files indexed (approximately 200-500 bytes per file)

## Troubleshooting

### Common Issues

1. **Permission Errors**: Run with appropriate permissions or skip inaccessible directories
2. **Large File Processing**: Be patient with large files; checksum calculation takes time
3. **Database Locks**: Ensure only one process accesses the database at a time

### Error Messages

- `"Directory does not exist"`: Check the directory path
- `"Error reading file"`: File permissions or I/O issues
- `"Error accessing file"`: File may be locked or have permission issues

## Contributing

Feel free to submit issues, feature requests, or pull requests to improve the file indexer.

## License

This project is open source. Use it according to your needs. 