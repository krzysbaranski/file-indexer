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

# Index the test directory
echo "1. Indexing test_files directory..."
./file-indexer -dir test_files -content
echo

# Show statistics
echo "2. Showing index statistics..."
./file-indexer -stats
echo

# List all indexed files
echo "3. Listing all indexed files..."
./file-indexer -list
echo

# Search for files containing "TODO"
echo "4. Searching for files containing 'TODO'..."
./file-indexer -search "TODO"
echo

# Search for Python files
echo "5. Searching for Python files..."
./file-indexer -search ".py"
echo

# Search for files with "test" in the name
echo "6. Searching for files with 'test' in the name..."
./file-indexer -search "test"
echo

echo "Example completed!"
echo "You can explore the generated file_index.json to see the index structure."