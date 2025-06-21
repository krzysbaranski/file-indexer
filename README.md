# File Indexer using DuckDB

A Python-based file indexing system that creates and maintains a DuckDB database of files with their metadata, including checksums, modification dates, and file sizes.

## Project Structure

```
file-index/
├── pyproject.toml          # Poetry configuration and dependencies
├── README.md               # This file
├── requirements.txt        # Pip requirements (for non-Poetry users)
├── file_indexer/          # Main package
│   ├── __init__.py        # Package initialization
│   ├── cli.py             # Command-line interface
│   └── indexer.py         # Core indexing functionality
├── examples/              # Usage examples
│   └── example_usage.py   # Programmatic usage example
└── tests/                 # Test suite
    └── __init__.py
```

## Features

- **Comprehensive File Metadata**: Tracks file path, filename, SHA256 checksum, modification datetime, and file size
- **Efficient Storage**: Uses DuckDB for high-performance analytical queries
- **Duplicate Detection**: Find files with identical content using checksum comparison
- **Flexible Search**: Search files by name patterns, paths, or checksums
- **Incremental Updates**: Only recalculates checksums for modified files
- **Command Line Interface**: Easy-to-use CLI for common operations
- **Programmatic API**: Full Python API for custom integrations

## Installation

### Using Poetry (Recommended)

1. Install Poetry if you haven't already:
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

2. Install the project and dependencies:
```bash
poetry install
```

3. Activate the virtual environment:
```bash
poetry shell
```

### Using pip

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
# Using Poetry
poetry run file-indexer --scan .

# Or with Poetry shell activated
file-indexer --scan .

# Using direct Python execution
python -m file_indexer.cli --scan .

# Index a specific directory
file-indexer --scan /path/to/directory

# Index without recursion (current directory only)
file-indexer --scan /path/to/directory --no-recursive

# Use custom database file
file-indexer --db custom_index.db --scan /path/to/directory
```

#### Search Files
```bash
# Search by filename pattern
file-indexer --search-filename "*.py"

# Search by path pattern
file-indexer --search-path "*Documents*"

# Search by exact checksum
file-indexer --search-checksum abc123def456...

# Combine multiple search criteria
file-indexer --search-filename "*.txt" --search-path "*backup*"
```

#### Find Duplicates
```bash
# Find all duplicate files
file-indexer --find-duplicates
```

#### Database Statistics
```bash
# Show database statistics
file-indexer --stats
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
```bash
# Run the example script with Poetry
poetry run python examples/example_usage.py

# Or with Poetry shell activated
python examples/example_usage.py
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
- **Symbolic Links**: Symbolic links are ignored and not indexed to avoid potential issues with broken links and circular references.
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

## Development

### Setting up for Development

1. Clone the repository and install development dependencies:
```bash
git clone <repository-url>
cd file-index
poetry install
```

2. Activate the virtual environment:
```bash
poetry shell
```

### Code Quality Tools

The project includes several development tools:

```bash
# Format code with Black
poetry run black file_indexer/ examples/ tests/

# Sort imports with isort
poetry run isort file_indexer/ examples/ tests/

# Lint code with flake8
poetry run flake8 file_indexer/ examples/ tests/

# Run tests
poetry run pytest
```

### Running Tests

```bash
# Run all tests
poetry run pytest

# Run tests with coverage
poetry run pytest --cov=file_indexer
```

## Contributing

Feel free to submit issues, feature requests, or pull requests to improve the file indexer.

## License

This project is open source. Use it according to your needs. 