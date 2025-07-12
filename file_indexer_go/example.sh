#!/bin/bash

# File Indexer Tool - Example Usage Script

echo "File Indexer Tool - Example Usage"
echo "================================="
echo

# Create some test files
echo "Creating test files..."
mkdir -p test_files
echo "This is a test file with TODO comment" > test_files/test1.txt
echo "Another file with some content" > test_files/test2.txt
echo "Python script with TODO" > test_files/script.py
echo "Configuration file" > test_files/config.json
mkdir -p test_files/subdir
echo "File in subdirectory" > test_files/subdir/file.txt

echo "Test files created in test_files/ directory"
echo

# Index the test directory (JSON storage)
echo "1. Indexing test_files directory with JSON storage..."
./file_indexer_go -dir test_files -content
echo

# Show statistics
echo "2. Showing index statistics..."
./file_indexer_go -stats
echo

# List all indexed files
echo "3. Listing all indexed files..."
./file_indexer_go -list
echo

# Search for files containing "TODO"
echo "4. Searching for files containing 'TODO'..."
./file_indexer_go -search "TODO"
echo

# Search for Python files
echo "5. Searching for Python files..."
./file_indexer_go -search ".py"
echo

# Search for files with "test" in the name
echo "6. Searching for files with 'test' in the name..."
./file_indexer_go -search "test"
echo

# Index with DuckDB backend
echo "7. Indexing with DuckDB backend..."
./file_indexer_go -db -dir test_files
echo

# Show DuckDB statistics
echo "8. Showing DuckDB statistics..."
./file_indexer_go -db -stats
echo

# Execute SQL queries
echo "9. Executing SQL queries on DuckDB..."
echo "   - Files larger than 10 bytes:"
./file_indexer_go -db -sql "SELECT filename, file_size FROM files WHERE file_size > 10"
echo

echo "   - Files with .txt extension:"
./file_indexer_go -db -sql "SELECT filename, path FROM files WHERE filename LIKE '%.txt'"
echo

echo "   - File count by extension:"
./file_indexer_go -db -sql "SELECT SUBSTR(filename, LENGTH(filename) - LOCATE('.', REVERSE(filename)) + 1) as extension, COUNT(*) as count FROM files GROUP BY extension ORDER BY count DESC"
echo

echo "Example completed!"
echo "You can explore the generated files:"
echo "  - file_index.json (JSON storage)"
echo "  - file_index.db (DuckDB database)"