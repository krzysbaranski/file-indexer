package indexer

import (
	"crypto/md5"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"io/fs"
	"log"
	"os"
	"path/filepath"
	"strings"
	"time"

	"file_indexer_go/db"
	"file_indexer_go/models"
)

// Indexer handles file indexing operations
type Indexer struct {
	index     *models.Index
	indexPath string
	db        *db.Database
	useDB     bool
}

// NewIndexer creates a new file indexer
func NewIndexer(indexPath string, useDB bool) *Indexer {
	return &Indexer{
		index: &models.Index{
			Files: make(map[string]models.FileInfo),
		},
		indexPath: indexPath,
		useDB:     useDB,
		db:        db.NewDatabase(),
	}
}

// InitDatabase initializes the database if using DB mode
func (i *Indexer) InitDatabase() error {
	if !i.useDB {
		return nil
	}
	return i.db.Init(i.indexPath)
}

// CloseDatabase closes the database connection
func (i *Indexer) CloseDatabase() error {
	if i.useDB {
		return i.db.Close()
	}
	return nil
}

// IndexDirectory recursively indexes all files in the given directory
func (i *Indexer) IndexDirectory(rootPath string, maxFileSize int64) error {
	if i.useDB {
		return i.indexDirectoryDB(rootPath, maxFileSize)
	}
	return i.indexDirectoryJSON(rootPath, maxFileSize)
}

// indexDirectoryDB indexes files using DuckDB
func (i *Indexer) indexDirectoryDB(rootPath string, maxFileSize int64) error {
	// Clear existing data
	if err := i.db.ClearData(); err != nil {
		return err
	}

	// Set metadata
	if err := i.db.SetMetadata("root_path", rootPath); err != nil {
		return err
	}
	if err := i.db.SetMetadata("indexed", time.Now().Format(time.RFC3339)); err != nil {
		return err
	}

	log.Printf("Starting to index directory: %s", rootPath)

	err := filepath.WalkDir(rootPath, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			log.Printf("Error accessing path %s: %v", path, err)
			return nil // Continue with other files
		}
		info, err := d.Info()
		if err != nil {
			log.Printf("Error getting file info for %s: %v", path, err)
			return nil // Continue with other files
		}

		// Check if the file should be skipped
		skip, err := shouldSkipFile(path, d)
		if err != nil {
			log.Printf("Error during file filtering for %s: %v", path, err)
			return nil // Continue with other files
		}
		if skip {
			log.Printf("Skipping file: %s:", path)
			return nil
		}

		// Skip files larger than maxFileSize
		if maxFileSize > 0 && info.Size() > maxFileSize {
			log.Printf("Skipping large file: %s (size: %d bytes)", path, info.Size())
			return nil
		}

		// Get absolute path
		absPath, err := filepath.Abs(path)
		if err != nil {
			log.Printf("Error getting absolute path for %s: %v", path, err)
			absPath = path // fallback to original path
		}

		// Calculate checksum
		log.Printf("Adding file: %s, size: %d", absPath, info.Size())
		checksum, err := i.calculateChecksum(path)
		if err != nil {
			log.Printf("Error calculating checksum for %s: %v", path, err)
			checksum = "" // empty checksum on error
		}

		fileInfo := models.FileInfo{
			Path:                 absPath,
			Filename:             filepath.Base(path),
			Checksum:             checksum,
			ModificationDateTime: info.ModTime(),
			FileSize:             info.Size(),
			IndexedAt:            time.Now(),
		}

		// Insert into database
		if err := i.db.InsertFile(fileInfo); err != nil {
			log.Printf("Error inserting file %s: %v", path, err)
			return nil
		}

		log.Printf("Indexed file: %s (size: %d bytes)", path, info.Size())

		return nil
	})

	if err != nil {
		return fmt.Errorf("error walking directory: %v", err)
	}

	// Get count of indexed files
	stats, err := i.db.GetStats()
	if err != nil {
		log.Printf("Error getting file count: %v", err)
	} else {
		log.Printf("Indexing completed. Total files indexed: %v", stats["total_files"])
	}

	return nil
}

// indexDirectoryJSON indexes files using JSON storage (original method)
func (i *Indexer) indexDirectoryJSON(rootPath string, maxFileSize int64) error {
	i.index.RootPath = rootPath
	i.index.Indexed = time.Now()

	log.Printf("Starting to index directory: %s", rootPath)

	err := filepath.WalkDir(rootPath, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			log.Printf("Error accessing path %s: %v", path, err)
			return nil // Continue with other files
		}

		info, err := d.Info()
		if err != nil {
			log.Printf("Error during accsssing file %s: %v", path, err)
			return nil
		}
		skip, err := shouldSkipFile(path, d)
		if err != nil {
			log.Printf("Error during file filtering for %s: %v", path, err)
			return nil
		}
		if skip {
			log.Printf("Skipping file: %s:", path)
			return nil // skip file
		}

		// Skip files larger than maxFileSize
		if maxFileSize > 0 && info.Size() > maxFileSize {
			log.Printf("Skipping large file: %s (size: %d bytes)", path, info.Size())
			return nil
		}

		// Get absolute path
		absPath, err := filepath.Abs(path)
		if err != nil {
			log.Printf("Error getting absolute path for %s: %v", path, err)
			absPath = path // fallback to original path
		}

		// Calculate checksum
		checksum, err := i.calculateChecksum(path)
		if err != nil {
			log.Printf("Error calculating checksum for %s: %v", path, err)
			checksum = "" // empty checksum on error
		}

		fileInfo := models.FileInfo{
			Path:                 absPath,
			Filename:             filepath.Base(path),
			Checksum:             checksum,
			ModificationDateTime: info.ModTime(),
			FileSize:             info.Size(),
			IndexedAt:            time.Now(),
		}

		i.index.Files[absPath] = fileInfo

		log.Printf("Indexed file: %s (size: %d bytes)", path, info.Size())

		return nil
	})

	if err != nil {
		return fmt.Errorf("error walking directory: %v", err)
	}

	log.Printf("Indexing completed. Total files indexed: %d", len(i.index.Files))
	return nil
}

func shouldSkipFile(path string, d fs.DirEntry) (bool, error) {
	// Skip hidden files and directories
	if strings.HasPrefix(filepath.Base(path), ".") {
		if d.IsDir() {
			return true, nil
		}
		return true, nil
	}

	// Skip directories - we only index files
	if d.IsDir() {
		return true, nil
	}

	info, err := d.Info()
	if err != nil {
		log.Printf("Error getting file info for %s: %v", path, err)
		return true, err
	}

	// Skip special files (symlinks, etc.)
	if !info.Mode().IsRegular() {
		log.Printf("Skipping special file: %s", path)
		return true, nil
	}
	return false, nil
}

// calculateChecksum calculates MD5 checksum of a file
func (i *Indexer) calculateChecksum(path string) (string, error) {
	file, err := os.Open(path)
	if err != nil {
		return "", err
	}

	hash := md5.New()
	_, err = io.Copy(hash, file)

	// Now, close the file and capture the error.
	closeErr := file.Close()

	// The error from the primary operation (copying) is more important.
	if err != nil {
		return "", err
	}

	// If copying succeeded, return the error from closing the file, if any.
	if closeErr != nil {
		return "", closeErr
	}

	return hex.EncodeToString(hash.Sum(nil)), nil
}

// SaveIndex saves the index to storage
func (i *Indexer) SaveIndex() error {
	if i.useDB {
		return nil // Database is already saved during indexing
	}
	return i.saveIndexJSON()
}

// saveIndexJSON saves the index to a JSON file
func (i *Indexer) saveIndexJSON() error {
	data, err := json.MarshalIndent(i.index, "", "  ")
	if err != nil {
		return fmt.Errorf("error marshaling index: %v", err)
	}

	err = os.WriteFile(i.indexPath, data, 0644)
	if err != nil {
		return fmt.Errorf("error writing index file: %v", err)
	}

	log.Printf("Index saved to: %s", i.indexPath)
	return nil
}

// LoadIndex loads the index from storage
func (i *Indexer) LoadIndex() error {
	if i.useDB {
		return i.loadIndexDB()
	}
	return i.loadIndexJSON()
}

// loadIndexDB loads the index from database (not needed for DB mode)
func (i *Indexer) loadIndexDB() error {
	// For database mode, we don't need to load anything into memory
	// as all operations are done directly on the database
	return nil
}

// loadIndexJSON loads the index from a JSON file
func (i *Indexer) loadIndexJSON() error {
	data, err := os.ReadFile(i.indexPath)
	if err != nil {
		return fmt.Errorf("error reading index file: %v", err)
	}

	err = json.Unmarshal(data, i.index)
	if err != nil {
		return fmt.Errorf("error unmarshaling index: %v", err)
	}

	log.Printf("Index loaded from: %s", i.indexPath)
	return nil
}

// Search searches for files matching the query
func (i *Indexer) Search(query string) []models.FileInfo {
	if i.useDB {
		return i.searchDB(query)
	}
	return i.searchJSON(query)
}

// searchDB searches for files in the database
func (i *Indexer) searchDB(query string) []models.FileInfo {
	files, err := i.db.SearchFiles(query)
	if err != nil {
		log.Printf("Error searching database: %v", err)
		return []models.FileInfo{}
	}
	return files
}

// searchJSON searches for files in the JSON index
func (i *Indexer) searchJSON(query string) []models.FileInfo {
	var results []models.FileInfo
	query = strings.ToLower(query)

	for _, file := range i.index.Files {
		if strings.Contains(strings.ToLower(file.Filename), query) ||
			strings.Contains(strings.ToLower(file.Path), query) {
			results = append(results, file)
		}
	}

	return results
}

// ListFiles returns all indexed files
func (i *Indexer) ListFiles() []models.FileInfo {
	if i.useDB {
		return i.listFilesDB()
	}
	return i.listFilesJSON()
}

// listFilesDB lists all files from the database
func (i *Indexer) listFilesDB() []models.FileInfo {
	files, err := i.db.ListFiles()
	if err != nil {
		log.Printf("Error listing files from database: %v", err)
		return []models.FileInfo{}
	}
	return files
}

// listFilesJSON lists all files from the JSON index
func (i *Indexer) listFilesJSON() []models.FileInfo {
	var files []models.FileInfo
	for _, file := range i.index.Files {
		files = append(files, file)
	}
	return files
}

// GetStats returns statistics about the index
func (i *Indexer) GetStats() map[string]interface{} {
	if i.useDB {
		return i.getStatsDB()
	}
	return i.getStatsJSON()
}

// getStatsDB gets statistics from the database
func (i *Indexer) getStatsDB() map[string]interface{} {
	stats, err := i.db.GetStats()
	if err != nil {
		log.Printf("Error getting database stats: %v", err)
		return map[string]interface{}{
			"error": "Failed to get database statistics",
		}
	}
	return stats
}

// getStatsJSON gets statistics from the JSON index
func (i *Indexer) getStatsJSON() map[string]interface{} {
	stats := make(map[string]interface{})
	stats["total_files"] = len(i.index.Files)
	stats["indexed_time"] = i.index.Indexed
	stats["root_path"] = i.index.RootPath

	var totalSize int64
	fileTypes := make(map[string]int)

	for _, file := range i.index.Files {
		totalSize += file.FileSize

		// Extract extension from filename
		ext := strings.ToLower(filepath.Ext(file.Filename))
		if ext == "" {
			fileTypes["no_extension"]++
		} else {
			fileTypes[ext]++
		}
	}

	stats["total_size"] = totalSize
	stats["file_types"] = fileTypes

	return stats
}

// GetFileByPathAndFilename retrieves a file by its path and filename.
func (i *Indexer) GetFileByPathAndFilename(path, filename string) (*models.FileInfo, error) {
	if i.useDB {
		return i.db.GetFileByPathAndFilename(path, filename)
	}

	// For JSON index, search through the files
	for _, file := range i.index.Files {
		if file.Path == path && file.Filename == filename {
			return &file, nil
		}
	}

	return nil, nil // Not found
}

// ExecuteSQL executes a custom SQL query (database mode only)
func (i *Indexer) ExecuteSQL(sqlQuery string) error {
	if !i.useDB {
		return fmt.Errorf("SQL queries are only available in database mode")
	}
	return i.db.ExecuteSQL(sqlQuery)
}
