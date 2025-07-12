package main

import (
	"bufio"
	"encoding/json"
	"flag"
	"fmt"
	"io/fs"
	"log"
	"os"
	"path/filepath"
	"strings"
	"time"
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

// Index represents the file index
type Index struct {
	Files    map[string]FileInfo `json:"files"`
	Indexed  time.Time           `json:"indexed"`
	RootPath string              `json:"root_path"`
}

// FileIndexer handles file indexing operations
type FileIndexer struct {
	index     *Index
	indexPath string
}

// NewFileIndexer creates a new file indexer
func NewFileIndexer(indexPath string) *FileIndexer {
	return &FileIndexer{
		index: &Index{
			Files: make(map[string]FileInfo),
		},
		indexPath: indexPath,
	}
}

// IndexDirectory recursively indexes all files in the given directory
func (fi *FileIndexer) IndexDirectory(rootPath string, includeContent bool, maxFileSize int64) error {
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

// SaveIndex saves the index to a JSON file
func (fi *FileIndexer) SaveIndex() error {
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

// LoadIndex loads an index from a JSON file
func (fi *FileIndexer) LoadIndex() error {
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
	var files []FileInfo
	for _, file := range fi.index.Files {
		files = append(files, file)
	}
	return files
}

// GetStats returns statistics about the index
func (fi *FileIndexer) GetStats() map[string]interface{} {
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

func main() {
	var (
		indexPath     = flag.String("index", "file_index.json", "Path to the index file")
		directory     = flag.String("dir", "", "Directory to index")
		searchQuery   = flag.String("search", "", "Search query")
		listFiles     = flag.Bool("list", false, "List all indexed files")
		showStats     = flag.Bool("stats", false, "Show index statistics")
		includeContent = flag.Bool("content", false, "Include file content in index")
		maxFileSize   = flag.Int64("max-size", 1024*1024, "Maximum file size to index (in bytes)")
	)
	flag.Parse()

	indexer := NewFileIndexer(*indexPath)

	// If no specific action is requested, show help
	if *directory == "" && *searchQuery == "" && !*listFiles && !*showStats {
		fmt.Println("File Indexer Tool")
		fmt.Println("=================")
		fmt.Println()
		fmt.Println("Usage:")
		fmt.Println("  Index a directory:")
		fmt.Println("    ./file-indexer -dir /path/to/directory [-content] [-max-size 1048576]")
		fmt.Println()
		fmt.Println("  Search for files:")
		fmt.Println("    ./file-indexer -search 'query'")
		fmt.Println()
		fmt.Println("  List all indexed files:")
		fmt.Println("    ./file-indexer -list")
		fmt.Println()
		fmt.Println("  Show statistics:")
		fmt.Println("    ./file-indexer -stats")
		fmt.Println()
		fmt.Println("Options:")
		flag.PrintDefaults()
		return
	}

	// Load existing index if it exists
	if _, err := os.Stat(*indexPath); err == nil {
		if err := indexer.LoadIndex(); err != nil {
			log.Printf("Warning: Could not load existing index: %v", err)
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