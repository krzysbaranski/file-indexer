# File Indexer Tool (Go)

A fast and efficient file indexing tool written in Go that allows you to index directories, search through files, and maintain a persistent index. Supports both JSON file storage and DuckDB database backend.

## Features

- **Directory Indexing**: Recursively index all files in a directory
- **Content Search**: Search through file names, paths, and content
- **Dual Storage Options**: JSON file storage or DuckDB database backend
- **File Filtering**: Skip hidden files and large files
- **Statistics**: Get detailed statistics about indexed files
- **Flexible Options**: Configurable file size limits and content inclusion
- **SQL Queries**: Execute custom SQL queries when using DuckDB backend
- **Cross-platform**: Works on Linux, macOS, and Windows

## Building

```bash
# Build the executable
go build -o file_indexer_go

# Or build with specific flags
go build -ldflags="-s -w" -o file_indexer_go
```

## Installation

### Prerequisites
- Go 1.24 or later
- DuckDB Go bindings (automatically managed via go.mod)

### Build and Install
```bash
cd file_indexer_go
go build
```

## Usage

### Basic Commands

```bash
# Show help
./file_indexer_go

# Index a directory (JSON storage)
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

### Command Line Options

- `-index string`: Path to the index file (default: "file_index.json")
- `-dir string`: Directory to index
- `-search string`: Search query
- `-list`: List all indexed files
- `-stats`: Show index statistics
- `-content`: Include file content in index
- `-max-size int`: Maximum file size to index in bytes (default: 1048576)
- `-db`: Use DuckDB database backend
- `-sql string`: Execute custom SQL query (database mode only)

### Examples

#### Index a directory with content
```bash
./file_indexer_go -dir /home/user/documents -content -max-size 2097152
```

#### Search for files containing "TODO"
```bash
./file_indexer_go -search "TODO"
```

#### Search for Python files
```bash
./file_indexer_go -search ".py"
```

#### Show statistics about the index
```bash
./file_indexer_go -stats
```

#### Use DuckDB backend for large datasets
```bash
./file_indexer_go -db -dir /path/to/large/directory
```

#### Execute custom SQL queries
```bash
# Find all files larger than 10MB
./file_indexer_go -db -sql "SELECT * FROM files WHERE size > 10485760"

# Find files modified in the last 7 days
./file_indexer_go -db -sql "SELECT * FROM files WHERE modification_datetime > datetime('now', '-7 days')"

# Get file count by extension
./file_indexer_go -db -sql "SELECT extension, COUNT(*) as count FROM files GROUP BY extension ORDER BY count DESC"
```

## Storage Options

### JSON File Storage (Default)
- Simple, portable storage format
- Good for small to medium datasets
- Easy to inspect and modify manually
- No external dependencies

### DuckDB Database Backend
- High-performance SQL database
- Suitable for large datasets
- Advanced querying capabilities
- ACID compliance and data integrity

## Index File Format

### JSON Storage Format
The tool creates a JSON file with the following structure:

```json
{
  "files": {
    "/path/to/file.txt": {
      "path": "/path/to/file.txt",
      "name": "file.txt",
      "size": 1024,
      "mod_time": "2023-01-01T12:00:00Z",
      "is_dir": false,
      "extension": ".txt",
      "content_lines": ["line 1", "line 2", "..."]
    }
  },
  "indexed": "2023-01-01T12:00:00Z",
  "root_path": "/path/to/directory"
}
```

### DuckDB Schema
When using the `-db` flag, the tool creates a DuckDB database with the following schema:

```sql
CREATE TABLE files (
    path VARCHAR NOT NULL,
    filename VARCHAR NOT NULL,
    checksum VARCHAR,
    modification_datetime TIMESTAMP NOT NULL,
    file_size BIGINT NOT NULL,
    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (path, filename)
);
```

## Features

### File Filtering
- Automatically skips hidden files and directories (starting with ".")
- Configurable maximum file size limit
- Skips files that are too large to process efficiently
- Filters out non-regular files (symlinks, devices, etc.)

### Search Capabilities
- Search by filename
- Search by file path
- Search within file content (when content is indexed)
- Case-insensitive search
- SQL queries when using DuckDB backend

### Performance
- Efficient file walking using Go's `filepath.WalkDir`
- Memory-efficient content reading
- Fast JSON serialization/deserialization
- Optimized DuckDB queries

### Error Handling
- Graceful handling of permission errors
- Continues indexing even if individual files fail
- Detailed logging of operations
- Automatic fallback for file access issues

## Dependencies

### Core Dependencies
- `github.com/marcboeker/go-duckdb`: DuckDB Go bindings for database backend
- Standard library packages:
  - `bufio`: For reading file content
  - `encoding/json`: For index serialization
  - `flag`: For command line argument parsing
  - `io/fs`: For file system operations
  - `log`: For logging
  - `os`: For file operations
  - `path/filepath`: For path manipulation
  - `strings`: For string operations
  - `time`: For timestamps

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

### Build Issues
If you encounter build issues, ensure you have the correct Go version:
```bash
go version  # Should be 1.24 or later
```

### Permission Issues
If you encounter permission errors:
- Ensure the target directory is readable
- Check file permissions for the output index file
- Use appropriate user permissions for the target directories

## Limitations

- File content is stored in memory, so very large indexes may consume significant memory
- Binary files are not indexed for content (only metadata)
- No incremental updates (re-indexing overwrites the entire index)
- JSON storage is not suitable for very large datasets (use DuckDB backend instead)

## Performance Tips

1. **Use DuckDB backend** for large datasets and advanced queries
2. **Limit content indexing** to text files for better performance
3. **Set appropriate max-size limits** to avoid memory issues
4. **Use JSON storage** for simple use cases and portability
5. **Avoid indexing very large files** unless necessary
6. **Use specific search queries** rather than broad searches for better performance

## License

This project is open source and available under the MIT License.