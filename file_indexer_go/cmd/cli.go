package cmd

import (
	"flag"
	"fmt"
	"log"
	"os"
	"strings"

	"file_indexer_go/indexer"
)

// CLI handles command-line interface operations
type CLI struct {
	indexer *indexer.Indexer
}

// NewCLI creates a new CLI instance
func NewCLI(indexer *indexer.Indexer) *CLI {
	return &CLI{
		indexer: indexer,
	}
}

// Config holds the CLI configuration
type Config struct {
	IndexPath     string
	Directory     string
	SearchQuery   string
	ListFiles     bool
	ShowStats     bool
	IncludeContent bool
	MaxFileSize   int64
	UseDB         bool
	SQLQuery      string
}

// ParseFlags parses command-line flags and returns configuration
func ParseFlags() *Config {
	var (
		indexPath     = flag.String("index", "file_index.json", "Path to the index file")
		directory     = flag.String("dir", "", "Directory to index")
		searchQuery   = flag.String("search", "", "Search query")
		listFiles     = flag.Bool("list", false, "List all indexed files")
		showStats     = flag.Bool("stats", false, "Show index statistics")
		includeContent = flag.Bool("content", false, "Include file content in index")
		maxFileSize   = flag.Int64("max-size", 0, "Maximum file size to index (in bytes, 0 = no limit)")
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

	return &Config{
		IndexPath:     actualIndexPath,
		Directory:     *directory,
		SearchQuery:   *searchQuery,
		ListFiles:     *listFiles,
		ShowStats:     *showStats,
		IncludeContent: *includeContent,
		MaxFileSize:   *maxFileSize,
		UseDB:         *useDB,
		SQLQuery:      *sqlQuery,
	}
}

// ShowHelp displays the help message
func ShowHelp() {
	fmt.Println("File Indexer Tool")
	fmt.Println("=================")
	fmt.Println()
	fmt.Println("Usage:")
	fmt.Println("  Index a directory:")
	fmt.Println("    ./file-indexer -dir /path/to/directory [-content] [-max-size SIZE] [-db]")
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
}

// Run executes the CLI based on the provided configuration
func (c *CLI) Run(config *Config) error {
	// Initialize database if needed
	if config.UseDB {
		if err := c.indexer.InitDatabase(); err != nil {
			return fmt.Errorf("error initializing database: %v", err)
		}
		defer c.indexer.CloseDatabase()
	}

	// Load existing index if it exists and no specific action is requested
	if config.Directory == "" {
		if _, err := os.Stat(config.IndexPath); err == nil {
			if err := c.indexer.LoadIndex(); err != nil {
				log.Printf("Warning: Could not load existing index: %v", err)
			}
		}
	}

	// Index directory
	if config.Directory != "" {
		if err := c.indexer.IndexDirectory(config.Directory, config.IncludeContent, config.MaxFileSize); err != nil {
			return fmt.Errorf("error indexing directory: %v", err)
		}

		if err := c.indexer.SaveIndex(); err != nil {
			return fmt.Errorf("error saving index: %v", err)
		}
	}

	// Execute SQL query
	if config.SQLQuery != "" {
		if err := c.indexer.ExecuteSQL(config.SQLQuery); err != nil {
			return fmt.Errorf("error executing SQL: %v", err)
		}
	}

	// Search
	if config.SearchQuery != "" {
		return c.handleSearch(config.SearchQuery)
	}

	// List files
	if config.ListFiles {
		return c.handleListFiles()
	}

	// Show statistics
	if config.ShowStats {
		return c.handleShowStats()
	}

	return nil
}

// handleSearch handles the search operation
func (c *CLI) handleSearch(query string) error {
	results := c.indexer.Search(query)
	fmt.Printf("Search results for '%s':\n", query)
	fmt.Printf("Found %d files:\n\n", len(results))
	
	for i, file := range results {
		fmt.Printf("%d. %s", i+1, file.Path)
		fmt.Printf(" (%d bytes)", file.FileSize)
		fmt.Println()
	}
	return nil
}

// handleListFiles handles the list files operation
func (c *CLI) handleListFiles() error {
	files := c.indexer.ListFiles()
	fmt.Printf("Indexed files (%d total):\n\n", len(files))
	
	for i, file := range files {
		fmt.Printf("%d. %s", i+1, file.Path)
		fmt.Printf(" (%d bytes)", file.FileSize)
		fmt.Println()
	}
	return nil
}

// handleShowStats handles the show statistics operation
func (c *CLI) handleShowStats() error {
	stats := c.indexer.GetStats()
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
	return nil
}