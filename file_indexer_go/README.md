# File Indexer Tool (Go)

A simplified file indexing tool written in Go that allows you to index directories, search through files, and maintain a persistent index.

## Features

- **Directory Indexing**: Recursively index all files in a directory
- **Content Search**: Search through file names, paths, and content
- **Persistent Storage**: Save and load indexes as JSON files
- **File Filtering**: Skip hidden files and large files
- **Statistics**: Get detailed statistics about indexed files
- **Flexible Options**: Configurable file size limits and content inclusion

## Building

```bash
go build -o file-indexer main.go
```

## Usage

### Basic Commands

```bash
# Show help
./file-indexer

# Index a directory
./file-indexer -dir /path/to/directory

# Index with content (for searching within files)
./file-indexer -dir /path/to/directory -content

# Search for files
./file-indexer -search "query"

# List all indexed files
./file-indexer -list

# Show statistics
./file-indexer -stats
```

### Command Line Options

- `-index string`: Path to the index file (default: "file_index.json")
- `-dir string`: Directory to index
- `-search string`: Search query
- `-list`: List all indexed files
- `-stats`: Show index statistics
- `-content`: Include file content in index
- `-max-size int`: Maximum file size to index in bytes (default: 1048576)

### Examples

#### Index a directory with content
```bash
./file-indexer -dir /home/user/documents -content -max-size 2097152
```

#### Search for files containing "TODO"
```bash
./file-indexer -search "TODO"
```

#### Search for Python files
```bash
./file-indexer -search ".py"
```

#### Show statistics about the index
```bash
./file-indexer -stats
```

## Index File Format

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

## Features

### File Filtering
- Automatically skips hidden files and directories (starting with ".")
- Configurable maximum file size limit
- Skips files that are too large to process efficiently

### Search Capabilities
- Search by filename
- Search by file path
- Search within file content (when content is indexed)
- Case-insensitive search

### Performance
- Efficient file walking using Go's `filepath.WalkDir`
- Memory-efficient content reading
- JSON-based persistent storage

### Error Handling
- Graceful handling of permission errors
- Continues indexing even if individual files fail
- Detailed logging of operations

## Limitations

- File content is stored in memory, so very large indexes may consume significant memory
- Binary files are not indexed for content (only metadata)
- No incremental updates (re-indexing overwrites the entire index)

## Dependencies

This tool uses only Go standard library packages:
- `bufio`: For reading file content
- `encoding/json`: For index serialization
- `flag`: For command line argument parsing
- `io/fs`: For file system operations
- `log`: For logging
- `os`: For file operations
- `path/filepath`: For path manipulation
- `strings`: For string operations
- `time`: For timestamps

## License

This project is open source and available under the MIT License.