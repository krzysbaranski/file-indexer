package main

import (
	"fmt"
	"log"
	"os"
	"path/filepath"
)

// Example usage of the file indexer tool
func main() {
	fmt.Println("File Indexer Tool - Go Examples")
	fmt.Println("================================")
	fmt.Println()

	// Example 1: Basic indexing with JSON storage
	fmt.Println("Example 1: Basic indexing with JSON storage")
	fmt.Println("Command: ./file_indexer_go -dir /path/to/directory")
	fmt.Println("This creates a file_index.json with all indexed files")
	fmt.Println()

	// Example 2: Indexing with content for text search
	fmt.Println("Example 2: Indexing with content for text search")
	fmt.Println("Command: ./file_indexer_go -dir /path/to/directory -content")
	fmt.Println("This includes file content in the index for searching within files")
	fmt.Println()

	// Example 3: Setting maximum file size
	fmt.Println("Example 3: Setting maximum file size")
	fmt.Println("Command: ./file_indexer_go -dir /path/to/directory -max-size 2097152")
	fmt.Println("This limits indexing to files smaller than 2MB")
	fmt.Println()

	// Example 4: Using DuckDB backend
	fmt.Println("Example 4: Using DuckDB backend")
	fmt.Println("Command: ./file_indexer_go -db -dir /path/to/directory")
	fmt.Println("This creates a file_index.db database for large datasets")
	fmt.Println()

	// Example 5: Searching files
	fmt.Println("Example 5: Searching files")
	fmt.Println("Command: ./file_indexer_go -search \"query\"")
	fmt.Println("This searches for files containing the specified query")
	fmt.Println()

	// Example 6: Listing all indexed files
	fmt.Println("Example 6: Listing all indexed files")
	fmt.Println("Command: ./file_indexer_go -list")
	fmt.Println("This displays all files in the current index")
	fmt.Println()

	// Example 7: Showing statistics
	fmt.Println("Example 7: Showing statistics")
	fmt.Println("Command: ./file_indexer_go -stats")
	fmt.Println("This shows detailed statistics about the index")
	fmt.Println()

	// Example 8: SQL queries with DuckDB
	fmt.Println("Example 8: SQL queries with DuckDB")
	fmt.Println("Command: ./file_indexer_go -db -sql \"SELECT * FROM files WHERE size > 1000000\"")
	fmt.Println("This executes custom SQL queries on the database")
	fmt.Println()

	// Example 9: Complex SQL queries
	fmt.Println("Example 9: Complex SQL queries")
	fmt.Println("Find files modified in the last 7 days:")
	fmt.Println("./file_indexer_go -db -sql \"SELECT * FROM files WHERE modification_datetime > datetime('now', '-7 days')\"")
	fmt.Println()
	fmt.Println("Get file count by extension:")
	fmt.Println("./file_indexer_go -db -sql \"SELECT SUBSTR(filename, LENGTH(filename) - LOCATE('.', REVERSE(filename)) + 1) as extension, COUNT(*) as count FROM files GROUP BY extension ORDER BY count DESC\"")
	fmt.Println()

	// Example 10: Complete workflow
	fmt.Println("Example 10: Complete workflow")
	fmt.Println("1. Index a directory with DuckDB:")
	fmt.Println("   ./file_indexer_go -db -dir /path/to/directory")
	fmt.Println()
	fmt.Println("2. Show statistics:")
	fmt.Println("   ./file_indexer_go -db -stats")
	fmt.Println()
	fmt.Println("3. Search for specific files:")
	fmt.Println("   ./file_indexer_go -db -sql \"SELECT * FROM files WHERE filename LIKE '%.py'\"")
	fmt.Println()
	fmt.Println("4. Find large files:")
	fmt.Println("   ./file_indexer_go -db -sql \"SELECT filename, file_size FROM files WHERE file_size > 10485760 ORDER BY file_size DESC\"")
	fmt.Println()

	// Example 11: Performance tips
	fmt.Println("Example 11: Performance tips")
	fmt.Println("- Use DuckDB backend for datasets with >10,000 files")
	fmt.Println("- Set appropriate max-size limits to avoid memory issues")
	fmt.Println("- Use specific SQL queries rather than broad searches")
	fmt.Println("- Avoid indexing very large files unless necessary")
	fmt.Println("- Use JSON storage for simple use cases and portability")
	fmt.Println()

	// Example 12: Troubleshooting
	fmt.Println("Example 12: Troubleshooting")
	fmt.Println("If you encounter DuckDB module issues:")
	fmt.Println("   go clean -modcache")
	fmt.Println("   go mod download")
	fmt.Println("   go mod tidy")
	fmt.Println()
	fmt.Println("For permission errors:")
	fmt.Println("- Ensure target directory is readable")
	fmt.Println("- Check file permissions for output files")
	fmt.Println("- Use appropriate user permissions")
	fmt.Println()

	fmt.Println("For more examples, run: ./example.sh")
	fmt.Println("For help, run: ./file_indexer_go")
}

// Helper function to create test files for examples
func createTestFiles() error {
	testDir := "test_files"
	
	// Create test directory
	if err := os.MkdirAll(testDir, 0755); err != nil {
		return err
	}

	// Create test files
	testFiles := map[string]string{
		"test1.txt":     "This is a test file with TODO comment",
		"test2.txt":     "Another file with some content",
		"script.py":     "Python script with TODO",
		"config.json":   "Configuration file",
		"subdir/file.txt": "File in subdirectory",
	}

	for filename, content := range testFiles {
		fullPath := filepath.Join(testDir, filename)
		
		// Create subdirectory if needed
		dir := filepath.Dir(fullPath)
		if err := os.MkdirAll(dir, 0755); err != nil {
			return err
		}

		// Write file content
		if err := os.WriteFile(fullPath, []byte(content), 0644); err != nil {
			return err
		}
	}

	log.Printf("Test files created in %s/ directory", testDir)
	return nil
}