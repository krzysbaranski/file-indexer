package main

import (
	"bufio"
	"database/sql"
	"encoding/json"
	"flag"
	"fmt"
	"io/fs"
	"log"
	"os"
	"path/filepath"
	"strings"
	"time"

	_ "github.com/marcboeker/go-duckdb"
)

// FileInfo represents information about an indexed file
type FileInfo struct {
	Path         string    `json:"path"`
	Name         string    `json:"name"`
	Size         int64     `json:"size"`
	ModTime      time.Time `json:"mod_time"`
	IsDir        bool      `json:"is_dir"`
	Extension    string    `json:"extension"`
	ContentLines []string  `json:"content_lines,omitempty"`
}

// Index represents the file index (for JSON compatibility)
type Index struct {
	Files    map[string]FileInfo `json:"files"`
	Indexed  time.Time           `json:"indexed"`
	RootPath string              `json:"root_path"`
}

// FileIndexer handles file indexing operations
type FileIndexer struct {
	index     *Index
	indexPath string
	db        *sql.DB
	useDB     bool
}

// NewFileIndexer creates a new file indexer
func NewFileIndexer(indexPath string, useDB bool) *FileIndexer {
	return &FileIndexer{
		index: &Index{
			Files: make(map[string]FileInfo),
		},
		indexPath: indexPath,
		useDB:     useDB,
	}
}

// InitDatabase initializes the DuckDB database and creates tables
func (fi *FileIndexer) InitDatabase() error {
	if !fi.useDB {
		return nil
	}

	var err error
	fi.db, err = sql.Open("duckdb", fi.indexPath)
	if err != nil {
		return fmt.Errorf("error opening database: %v", err)
	}

	// Create tables
	createTablesSQL := `
	CREATE TABLE IF NOT EXISTS files (
		path VARCHAR PRIMARY KEY,
		name VARCHAR NOT NULL,
		size BIGINT NOT NULL,
		mod_time TIMESTAMP NOT NULL,
		is_dir BOOLEAN NOT NULL,
		extension VARCHAR,
		content_lines TEXT[]
	);
	
	CREATE TABLE IF NOT EXISTS index_metadata (
		key VARCHAR PRIMARY KEY,
		value VARCHAR
	);
	
	CREATE INDEX IF NOT EXISTS idx_files_name ON files(name);
	CREATE INDEX IF NOT EXISTS idx_files_extension ON files(extension);
	CREATE INDEX IF NOT EXISTS idx_files_is_dir ON files(is_dir);
	`

	_, err = fi.db.Exec(createTablesSQL)
	if err != nil {
		return fmt.Errorf("error creating tables: %v", err)
	}

	log.Printf("Database initialized: %s", fi.indexPath)
	return nil
}

// CloseDatabase closes the database connection
func (fi *FileIndexer) CloseDatabase() error {
	if fi.db != nil {
		return fi.db.Close()
	}
	return nil
}

// IndexDirectory recursively indexes all files in the given directory
func (fi *FileIndexer) IndexDirectory(rootPath string, includeContent bool, maxFileSize int64) error {
	if fi.useDB {
		return fi.indexDirectoryDB(rootPath, includeContent, maxFileSize)
	}
	return fi.indexDirectoryJSON(rootPath, includeContent, maxFileSize)
}

// indexDirectoryDB indexes files using DuckDB
func (fi *FileIndexer) indexDirectoryDB(rootPath string, includeContent bool, maxFileSize int64) error {
	// Clear existing data
	_, err := fi.db.Exec("DELETE FROM files")
	if err != nil {
		return fmt.Errorf("error clearing existing data: %v", err)
	}

	// Update metadata
	_, err = fi.db.Exec("DELETE FROM index_metadata")
	if err != nil {
		return fmt.Errorf("error clearing metadata: %v", err)
	}

	_, err = fi.db.Exec("INSERT INTO index_metadata (key, value) VALUES (?, ?)", "root_path", rootPath)
	if err != nil {
		return fmt.Errorf("error setting root_path: %v", err)
	}

	_, err = fi.db.Exec("INSERT INTO index_metadata (key, value) VALUES (?, ?)", "indexed", time.Now().Format(time.RFC3339))
	if err != nil {
		return fmt.Errorf("error setting indexed time: %v", err)
	}

	log.Printf("Starting to index directory: %s", rootPath)

	err = filepath.WalkDir(rootPath, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			log.Printf("Error accessing path %s: %v", path, err)
			return nil // Continue with other files
		}

		// Skip hidden files and directories
		if strings.HasPrefix(filepath.Base(path), ".") {
			if d.IsDir() {
				return filepath.SkipDir
			}
			return nil
		}

		info, err := d.Info()
		if err != nil {
			log.Printf("Error getting file info for %s: %v", path, err)
			return nil
		}

		// Skip files larger than maxFileSize
		if !d.IsDir() && maxFileSize > 0 && info.Size() > maxFileSize {
			log.Printf("Skipping large file: %s (size: %d bytes)", path, info.Size())
			return nil
		}

		var contentLines []string
		if includeContent && !d.IsDir() && info.Size() <= maxFileSize {
			content, err := fi.readFileContent(path)
			if err != nil {
				log.Printf("Error reading content of %s: %v", path, err)
			} else {
				contentLines = content
			}
		}

		// Insert into database
		_, err = fi.db.Exec(`
			INSERT INTO files (path, name, size, mod_time, is_dir, extension, content_lines)
			VALUES (?, ?, ?, ?, ?, ?, ?)
		`, path, filepath.Base(path), info.Size(), info.ModTime(), d.IsDir(), 
			strings.ToLower(filepath.Ext(path)), contentLines)

		if err != nil {
			log.Printf("Error inserting file %s: %v", path, err)
			return nil
		}

		if d.IsDir() {
			log.Printf("Indexed directory: %s", path)
		} else {
			log.Printf("Indexed file: %s (size: %d bytes)", path, info.Size())
		}

		return nil
	})

	if err != nil {
		return fmt.Errorf("error walking directory: %v", err)
	}

	// Get count of indexed files
	var count int
	err = fi.db.QueryRow("SELECT COUNT(*) FROM files").Scan(&count)
	if err != nil {
		log.Printf("Error getting file count: %v", err)
	} else {
		log.Printf("Indexing completed. Total files indexed: %d", count)
	}

	return nil
}

// indexDirectoryJSON indexes files using JSON storage (original method)
func (fi *FileIndexer) indexDirectoryJSON(rootPath string, includeContent bool, maxFileSize int64) error {
	fi.index.RootPath = rootPath
	fi.index.Indexed = time.Now()

	log.Printf("Starting to index directory: %s", rootPath)

	err := filepath.WalkDir(rootPath, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			log.Printf("Error accessing path %s: %v", path, err)
			return nil // Continue with other files
		}

		// Skip hidden files and directories
		if strings.HasPrefix(filepath.Base(path), ".") {
			if d.IsDir() {
				return filepath.SkipDir
			}
			return nil
		}

		info, err := d.Info()
		if err != nil {
			log.Printf("Error getting file info for %s: %v", path, err)
			return nil
		}

		// Skip files larger than maxFileSize
		if !d.IsDir() && maxFileSize > 0 && info.Size() > maxFileSize {
			log.Printf("Skipping large file: %s (size: %d bytes)", path, info.Size())
			return nil
		}

		fileInfo := FileInfo{
			Path:      path,
			Name:      filepath.Base(path),
			Size:      info.Size(),
			ModTime:   info.ModTime(),
			IsDir:     d.IsDir(),
			Extension: strings.ToLower(filepath.Ext(path)),
		}

		// Read file content if requested and file is not too large
		if includeContent && !d.IsDir() && info.Size() <= maxFileSize {
			content, err := fi.readFileContent(path)
			if err != nil {
				log.Printf("Error reading content of %s: %v", path, err)
			} else {
				fileInfo.ContentLines = content
			}
		}

		fi.index.Files[path] = fileInfo

		if d.IsDir() {
			log.Printf("Indexed directory: %s", path)
		} else {
			log.Printf("Indexed file: %s (size: %d bytes)", path, info.Size())
		}

		return nil
	})

	if err != nil {
		return fmt.Errorf("error walking directory: %v", err)
	}

	log.Printf("Indexing completed. Total files indexed: %d", len(fi.index.Files))
	return nil
}

// readFileContent reads the content of a file and returns it as lines
func (fi *FileIndexer) readFileContent(path string) ([]string, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer file.Close()

	var lines []string
	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		lines = append(lines, scanner.Text())
	}

	return lines, scanner.Err()
}

// SaveIndex saves the index
func (fi *FileIndexer) SaveIndex() error {
	if fi.useDB {
		// Database is already saved during indexing
		return nil
	}
	return fi.saveIndexJSON()
}

// saveIndexJSON saves the index to a JSON file
func (fi *FileIndexer) saveIndexJSON() error {
	data, err := json.MarshalIndent(fi.index, "", "  ")
	if err != nil {
		return fmt.Errorf("error marshaling index: %v", err)
	}

	err = os.WriteFile(fi.indexPath, data, 0644)
	if err != nil {
		return fmt.Errorf("error writing index file: %v", err)
	}

	log.Printf("Index saved to: %s", fi.indexPath)
	return nil
}

// LoadIndex loads an index
func (fi *FileIndexer) LoadIndex() error {
	if fi.useDB {
		return fi.loadIndexDB()
	}
	return fi.loadIndexJSON()
}

// loadIndexDB loads index from database
func (fi *FileIndexer) loadIndexDB() error {
	if fi.db == nil {
		return fmt.Errorf("database not initialized")
	}

	// Check if database has data
	var count int
	err := fi.db.QueryRow("SELECT COUNT(*) FROM files").Scan(&count)
	if err != nil {
		return fmt.Errorf("error checking database: %v", err)
	}

	if count == 0 {
		return fmt.Errorf("no data found in database")
	}

	log.Printf("Index loaded from database: %s", fi.indexPath)
	return nil
}

// loadIndexJSON loads an index from a JSON file
func (fi *FileIndexer) loadIndexJSON() error {
	data, err := os.ReadFile(fi.indexPath)
	if err != nil {
		return fmt.Errorf("error reading index file: %v", err)
	}

	err = json.Unmarshal(data, &fi.index)
	if err != nil {
		return fmt.Errorf("error unmarshaling index: %v", err)
	}

	log.Printf("Index loaded from: %s", fi.indexPath)
	return nil
}

// Search searches for files matching the given query
func (fi *FileIndexer) Search(query string) []FileInfo {
	if fi.useDB {
		return fi.searchDB(query)
	}
	return fi.searchJSON(query)
}

// searchDB searches using SQL
func (fi *FileIndexer) searchDB(query string) []FileInfo {
	query = strings.ToLower(query)
	var results []FileInfo

	// Search in filename, path, and content
	rows, err := fi.db.Query(`
		SELECT path, name, size, mod_time, is_dir, extension, content_lines
		FROM files
		WHERE LOWER(name) LIKE ? OR LOWER(path) LIKE ? OR 
		      EXISTS (SELECT 1 FROM unnest(content_lines) AS line WHERE LOWER(line) LIKE ?)
	`, "%"+query+"%", "%"+query+"%", "%"+query+"%")

	if err != nil {
		log.Printf("Error searching database: %v", err)
		return results
	}
	defer rows.Close()

	for rows.Next() {
		var file FileInfo
		var contentLines []string
		err := rows.Scan(&file.Path, &file.Name, &file.Size, &file.ModTime, 
			&file.IsDir, &file.Extension, &contentLines)
		if err != nil {
			log.Printf("Error scanning row: %v", err)
			continue
		}
		file.ContentLines = contentLines
		results = append(results, file)
	}

	return results
}

// searchJSON searches using JSON data
func (fi *FileIndexer) searchJSON(query string) []FileInfo {
	query = strings.ToLower(query)
	var results []FileInfo

	for _, file := range fi.index.Files {
		// Search in filename
		if strings.Contains(strings.ToLower(file.Name), query) {
			results = append(results, file)
			continue
		}

		// Search in path
		if strings.Contains(strings.ToLower(file.Path), query) {
			results = append(results, file)
			continue
		}

		// Search in content
		for _, line := range file.ContentLines {
			if strings.Contains(strings.ToLower(line), query) {
				results = append(results, file)
				break
			}
		}
	}

	return results
}

// ListFiles lists all indexed files
func (fi *FileIndexer) ListFiles() []FileInfo {
	if fi.useDB {
		return fi.listFilesDB()
	}
	return fi.listFilesJSON()
}

// listFilesDB lists files using SQL
func (fi *FileIndexer) listFilesDB() []FileInfo {
	var files []FileInfo

	rows, err := fi.db.Query("SELECT path, name, size, mod_time, is_dir, extension, content_lines FROM files ORDER BY path")
	if err != nil {
		log.Printf("Error listing files from database: %v", err)
		return files
	}
	defer rows.Close()

	for rows.Next() {
		var file FileInfo
		var contentLines []string
		err := rows.Scan(&file.Path, &file.Name, &file.Size, &file.ModTime, 
			&file.IsDir, &file.Extension, &contentLines)
		if err != nil {
			log.Printf("Error scanning row: %v", err)
			continue
		}
		file.ContentLines = contentLines
		files = append(files, file)
	}

	return files
}

// listFilesJSON lists files from JSON data
func (fi *FileIndexer) listFilesJSON() []FileInfo {
	var files []FileInfo
	for _, file := range fi.index.Files {
		files = append(files, file)
	}
	return files
}

// GetStats returns statistics about the index
func (fi *FileIndexer) GetStats() map[string]interface{} {
	if fi.useDB {
		return fi.getStatsDB()
	}
	return fi.getStatsJSON()
}

// getStatsDB gets statistics from database
func (fi *FileIndexer) getStatsDB() map[string]interface{} {
	stats := make(map[string]interface{})

	// Total files
	var totalFiles int
	err := fi.db.QueryRow("SELECT COUNT(*) FROM files").Scan(&totalFiles)
	if err != nil {
		log.Printf("Error getting total files: %v", err)
	}
	stats["total_files"] = totalFiles

	// Total size
	var totalSize int64
	err = fi.db.QueryRow("SELECT COALESCE(SUM(size), 0) FROM files WHERE is_dir = false").Scan(&totalSize)
	if err != nil {
		log.Printf("Error getting total size: %v", err)
	}
	stats["total_size"] = totalSize

	// File types
	rows, err := fi.db.Query("SELECT extension, COUNT(*) FROM files WHERE is_dir = false GROUP BY extension ORDER BY COUNT(*) DESC")
	if err != nil {
		log.Printf("Error getting file types: %v", err)
	} else {
		defer rows.Close()
		fileTypes := make(map[string]int)
		for rows.Next() {
			var ext string
			var count int
			if err := rows.Scan(&ext, &count); err == nil {
				fileTypes[ext] = count
			}
		}
		stats["file_types"] = fileTypes
	}

	// Metadata
	var rootPath, indexedTime string
	err = fi.db.QueryRow("SELECT value FROM index_metadata WHERE key = 'root_path'").Scan(&rootPath)
	if err == nil {
		stats["root_path"] = rootPath
	}

	err = fi.db.QueryRow("SELECT value FROM index_metadata WHERE key = 'indexed'").Scan(&indexedTime)
	if err == nil {
		if t, err := time.Parse(time.RFC3339, indexedTime); err == nil {
			stats["indexed_time"] = t
		}
	}

	return stats
}

// getStatsJSON gets statistics from JSON data
func (fi *FileIndexer) getStatsJSON() map[string]interface{} {
	totalFiles := len(fi.index.Files)
	totalSize := int64(0)
	fileTypes := make(map[string]int)

	for _, file := range fi.index.Files {
		if !file.IsDir {
			totalSize += file.Size
			fileTypes[file.Extension]++
		}
	}

	return map[string]interface{}{
		"total_files":   totalFiles,
		"total_size":    totalSize,
		"file_types":    fileTypes,
		"indexed_time":  fi.index.Indexed,
		"root_path":     fi.index.RootPath,
	}
}

// ExecuteSQL executes a custom SQL query (database mode only)
func (fi *FileIndexer) ExecuteSQL(sqlQuery string) error {
	if !fi.useDB {
		return fmt.Errorf("SQL queries are only available in database mode")
	}

	rows, err := fi.db.Query(sqlQuery)
	if err != nil {
		return fmt.Errorf("error executing SQL: %v", err)
	}
	defer rows.Close()

	columns, err := rows.Columns()
	if err != nil {
		return fmt.Errorf("error getting columns: %v", err)
	}

	// Print header
	fmt.Println(strings.Join(columns, " | "))

	// Print separator
	separator := ""
	for range columns {
		separator += "--- | "
	}
	fmt.Println(separator[:len(separator)-3])

	// Print data
	values := make([]interface{}, len(columns))
	valuePtrs := make([]interface{}, len(columns))
	for i := range values {
		valuePtrs[i] = &values[i]
	}

	for rows.Next() {
		err := rows.Scan(valuePtrs...)
		if err != nil {
			log.Printf("Error scanning row: %v", err)
			continue
		}

		row := make([]string, len(columns))
		for i, val := range values {
			if val == nil {
				row[i] = "NULL"
			} else {
				row[i] = fmt.Sprintf("%v", val)
			}
		}
		fmt.Println(strings.Join(row, " | "))
	}

	return nil
}

func main() {
	var (
		indexPath     = flag.String("index", "file_index.json", "Path to the index file")
		directory     = flag.String("dir", "", "Directory to index")
		searchQuery   = flag.String("search", "", "Search query")
		listFiles     = flag.Bool("list", false, "List all indexed files")
		showStats     = flag.Bool("stats", false, "Show index statistics")
		includeContent = flag.Bool("content", false, "Include file content in index")
		maxFileSize   = flag.Int64("max-size", 1024*1024, "Maximum file size to index (in bytes)")
		useDB         = flag.Bool("db", false, "Use DuckDB database backend")
		sqlQuery      = flag.String("sql", "", "Execute custom SQL query (database mode only)")
	)
	flag.Parse()

	// Adjust file path for database mode
	actualIndexPath := *indexPath
	if *useDB {
		// Change extension to .db for database files
		if strings.HasSuffix(actualIndexPath, ".json") {
			actualIndexPath = strings.TrimSuffix(actualIndexPath, ".json") + ".db"
		} else if !strings.HasSuffix(actualIndexPath, ".db") {
			actualIndexPath = actualIndexPath + ".db"
		}
	}

	indexer := NewFileIndexer(actualIndexPath, *useDB)

	// Initialize database if needed
	if *useDB {
		if err := indexer.InitDatabase(); err != nil {
			log.Fatalf("Error initializing database: %v", err)
		}
		defer indexer.CloseDatabase()
	}

	// If no specific action is requested, show help
	if *directory == "" && *searchQuery == "" && !*listFiles && !*showStats && *sqlQuery == "" {
		fmt.Println("File Indexer Tool")
		fmt.Println("=================")
		fmt.Println()
		fmt.Println("Usage:")
		fmt.Println("  Index a directory:")
		fmt.Println("    ./file-indexer -dir /path/to/directory [-content] [-max-size 1048576] [-db]")
		fmt.Println()
		fmt.Println("  Search for files:")
		fmt.Println("    ./file-indexer -search 'query' [-db]")
		fmt.Println()
		fmt.Println("  List all indexed files:")
		fmt.Println("    ./file-indexer -list [-db]")
		fmt.Println()
		fmt.Println("  Show statistics:")
		fmt.Println("    ./file-indexer -stats [-db]")
		fmt.Println()
		fmt.Println("  Execute SQL query (database mode only):")
		fmt.Println("    ./file-indexer -sql 'SELECT * FROM files LIMIT 10' -db")
		fmt.Println()
		fmt.Println("  Examples:")
		fmt.Println("    # Index with JSON storage (default)")
		fmt.Println("    ./file-indexer -dir /path/to/directory -content")
		fmt.Println()
		fmt.Println("    # Index with DuckDB database")
		fmt.Println("    ./file-indexer -dir /path/to/directory -content -db")
		fmt.Println()
		fmt.Println("    # Search in database")
		fmt.Println("    ./file-indexer -search 'TODO' -db")
		fmt.Println()
		fmt.Println("    # Custom SQL query")
		fmt.Println("    ./file-indexer -sql \"SELECT name, size FROM files WHERE size > 1000\" -db")
		fmt.Println()
		fmt.Println("Options:")
		flag.PrintDefaults()
		return
	}

	// Load existing index if it exists
	if *directory == "" {
		if _, err := os.Stat(actualIndexPath); err == nil {
			if err := indexer.LoadIndex(); err != nil {
				log.Printf("Warning: Could not load existing index: %v", err)
			}
		}
	}

	// Index directory
	if *directory != "" {
		if err := indexer.IndexDirectory(*directory, *includeContent, *maxFileSize); err != nil {
			log.Fatalf("Error indexing directory: %v", err)
		}

		if err := indexer.SaveIndex(); err != nil {
			log.Fatalf("Error saving index: %v", err)
		}
	}

	// Execute SQL query
	if *sqlQuery != "" {
		if err := indexer.ExecuteSQL(*sqlQuery); err != nil {
			log.Fatalf("Error executing SQL: %v", err)
		}
	}

	// Search
	if *searchQuery != "" {
		results := indexer.Search(*searchQuery)
		fmt.Printf("Search results for '%s':\n", *searchQuery)
		fmt.Printf("Found %d files:\n\n", len(results))
		
		for i, file := range results {
			fmt.Printf("%d. %s", i+1, file.Path)
			if file.IsDir {
				fmt.Print(" [DIR]")
			} else {
				fmt.Printf(" (%d bytes)", file.Size)
			}
			fmt.Println()
		}
	}

	// List files
	if *listFiles {
		files := indexer.ListFiles()
		fmt.Printf("Indexed files (%d total):\n\n", len(files))
		
		for i, file := range files {
			fmt.Printf("%d. %s", i+1, file.Path)
			if file.IsDir {
				fmt.Print(" [DIR]")
			} else {
				fmt.Printf(" (%d bytes)", file.Size)
			}
			fmt.Println()
		}
	}

	// Show statistics
	if *showStats {
		stats := indexer.GetStats()
		fmt.Println("Index Statistics:")
		fmt.Println("=================")
		fmt.Printf("Total files: %v\n", stats["total_files"])
		fmt.Printf("Total size: %v bytes\n", stats["total_size"])
		fmt.Printf("Indexed time: %v\n", stats["indexed_time"])
		fmt.Printf("Root path: %v\n", stats["root_path"])
		
		if fileTypes, ok := stats["file_types"].(map[string]int); ok {
			fmt.Println("\nFile types:")
			for ext, count := range fileTypes {
				if ext == "" {
					fmt.Printf("  No extension: %d\n", count)
				} else {
					fmt.Printf("  %s: %d\n", ext, count)
				}
			}
		}
	}
}