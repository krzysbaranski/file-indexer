package db

import (
	"database/sql"
	"fmt"
	"log"
	"strings"
	"time"

	"file_indexer_go/models"

	_ "github.com/marcboeker/go-duckdb/v2"
)

// Database handles all database operations
type Database struct {
	db *sql.DB
}

// NewDatabase creates a new database instance
func NewDatabase() *Database {
	return &Database{}
}

// Init initializes the DuckDB database and creates tables
func (d *Database) Init(dbPath string) error {
	var err error
	d.db, err = sql.Open("duckdb", dbPath)
	if err != nil {
		return fmt.Errorf("error opening database: %v", err)
	}

	// No special extensions needed for this schema

	// Create tables
	createTablesSQL := `
	CREATE TABLE IF NOT EXISTS files (
		path VARCHAR NOT NULL,
		filename VARCHAR NOT NULL,
		checksum VARCHAR,
		modification_datetime TIMESTAMP NOT NULL,
		file_size BIGINT NOT NULL,
		indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
		PRIMARY KEY (path, filename)
	);
	
	CREATE TABLE IF NOT EXISTS index_metadata (
		key VARCHAR PRIMARY KEY,
		value VARCHAR
	);
	
	CREATE INDEX IF NOT EXISTS idx_files_filename ON files(filename);
	CREATE INDEX IF NOT EXISTS idx_files_checksum ON files(checksum);
	`

	_, err = d.db.Exec(createTablesSQL)
	if err != nil {
		return fmt.Errorf("error creating tables: %v", err)
	}

	log.Printf("Database initialized: %s", dbPath)
	return nil
}

// Close closes the database connection
func (d *Database) Close() error {
	if d.db != nil {
		return d.db.Close()
	}
	return nil
}

// ClearData clears all existing data from the database
func (d *Database) ClearData() error {
	_, err := d.db.Exec("DELETE FROM files")
	if err != nil {
		return fmt.Errorf("error clearing existing data: %v", err)
	}

	_, err = d.db.Exec("DELETE FROM index_metadata")
	if err != nil {
		return fmt.Errorf("error clearing metadata: %v", err)
	}

	return nil
}

// SetMetadata sets metadata key-value pairs
func (d *Database) SetMetadata(key, value string) error {
	_, err := d.db.Exec("INSERT INTO index_metadata (key, value) VALUES (?, ?)", key, value)
	if err != nil {
		return fmt.Errorf("error setting %s: %v", key, err)
	}
	return nil
}

// InsertFile inserts a file record into the database
func (d *Database) InsertFile(file models.FileInfo) error {
	_, err := d.db.Exec(`
		INSERT INTO files (path, filename, checksum, modification_datetime, file_size, indexed_at)
		VALUES (?, ?, ?, ?, ?, ?)
		ON CONFLICT(path, filename) DO UPDATE SET
		checksum = excluded.checksum,
		modification_datetime = excluded.modification_datetime,
		file_size = excluded.file_size,
		indexed_at = excluded.indexed_at
	`, file.Path, file.Filename, file.Checksum, file.ModificationDateTime, file.FileSize, file.IndexedAt)

	if err != nil {
		return fmt.Errorf("error inserting file %s: %v", file.Path, err)
	}
	return nil
}

// SearchFiles searches for files in the database
func (d *Database) SearchFiles(query string) ([]models.FileInfo, error) {
	rows, err := d.db.Query(`
		SELECT path, filename, checksum, modification_datetime, file_size, indexed_at
		FROM files
		WHERE filename ILIKE ? OR path ILIKE ?
		ORDER BY filename
	`, "%"+query+"%", "%"+query+"%")
	if err != nil {
		return nil, fmt.Errorf("error searching files: %v", err)
	}
	defer rows.Close()

	var files []models.FileInfo
	for rows.Next() {
		var file models.FileInfo
		var checksumNullable sql.NullString
		err := rows.Scan(&file.Path, &file.Filename, &checksumNullable, &file.ModificationDateTime, &file.FileSize, &file.IndexedAt)
		if err != nil {
			log.Printf("Error scanning file row: %v", err)
			continue
		}

		// Handle nullable checksum
		if checksumNullable.Valid {
			file.Checksum = checksumNullable.String
		}

		files = append(files, file)
	}

	return files, nil
}

// ListFiles retrieves all files from the database
func (d *Database) ListFiles() ([]models.FileInfo, error) {
	rows, err := d.db.Query(`
		SELECT path, filename, checksum, modification_datetime, file_size, indexed_at
		FROM files
		ORDER BY filename
	`)
	if err != nil {
		return nil, fmt.Errorf("error listing files: %v", err)
	}
	defer rows.Close()

	var files []models.FileInfo
	for rows.Next() {
		var file models.FileInfo
		var checksumNullable sql.NullString
		err := rows.Scan(&file.Path, &file.Filename, &checksumNullable, &file.ModificationDateTime, &file.FileSize, &file.IndexedAt)
		if err != nil {
			log.Printf("Error scanning file row: %v", err)
			continue
		}

		// Handle nullable checksum
		if checksumNullable.Valid {
			file.Checksum = checksumNullable.String
		}

		files = append(files, file)
	}

	return files, nil
}

// GetFileByPathAndFilename retrieves a file by its path and filename.
func (d *Database) GetFileByPathAndFilename(path, filename string) (*models.FileInfo, error) {
	row := d.db.QueryRow("SELECT path, filename, checksum, modification_datetime, file_size, indexed_at FROM files WHERE path = ? AND filename = ?", path, filename)

	var file models.FileInfo
	err := row.Scan(&file.Path, &file.Filename, &file.Checksum, &file.ModificationDateTime, &file.FileSize, &file.IndexedAt)
	if err != nil {
		if err == sql.ErrNoRows {
			return nil, nil // Not found
		}
		return nil, fmt.Errorf("error scanning file info: %v", err)
	}

	return &file, nil
}

// GetStats retrieves statistics from the database
func (d *Database) GetStats() (map[string]interface{}, error) {
	stats := make(map[string]interface{})

	// Get total files count
	var totalFiles int
	err := d.db.QueryRow("SELECT COUNT(*) FROM files").Scan(&totalFiles)
	if err != nil {
		return nil, fmt.Errorf("error getting file count: %v", err)
	}
	stats["total_files"] = totalFiles

	// Get total size
	var totalSize int64
	err = d.db.QueryRow("SELECT COALESCE(SUM(file_size), 0) FROM files").Scan(&totalSize)
	if err != nil {
		return nil, fmt.Errorf("error getting total size: %v", err)
	}
	stats["total_size"] = totalSize

	// Get indexed time
	var indexedTimeStr string
	err = d.db.QueryRow("SELECT value FROM index_metadata WHERE key = 'indexed'").Scan(&indexedTimeStr)
	if err == nil {
		if indexedTime, err := time.Parse(time.RFC3339, indexedTimeStr); err == nil {
			stats["indexed_time"] = indexedTime
		}
	}

	// Get root path
	var rootPath string
	err = d.db.QueryRow("SELECT value FROM index_metadata WHERE key = 'root_path'").Scan(&rootPath)
	if err == nil {
		stats["root_path"] = rootPath
	}

	// Get file types distribution (extract extension from filename)
	rows, err := d.db.Query(`
		SELECT 
			CASE 
				WHEN filename LIKE '%.%' THEN SUBSTRING(filename, INSTR(filename, '.'))
				ELSE ''
			END as extension, 
			COUNT(*) as count
		FROM files
		GROUP BY extension
		ORDER BY count DESC
	`)
	if err != nil {
		log.Printf("Error getting file types: %v", err)
	} else {
		defer rows.Close()
		fileTypes := make(map[string]int)
		for rows.Next() {
			var ext string
			var count int
			if err := rows.Scan(&ext, &count); err == nil {
				if ext == "" {
					fileTypes["no_extension"] = count
				} else {
					fileTypes["."+ext] = count
				}
			}
		}
		stats["file_types"] = fileTypes
	}

	return stats, nil
}

// ExecuteSQL executes a custom SQL query and prints results
func (d *Database) ExecuteSQL(sqlQuery string) error {
	rows, err := d.db.Query(sqlQuery)
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
