package main

import (
	"log"

	"file_indexer_go/cmd"
	"file_indexer_go/indexer"
)

func main() {
	// Parse command-line flags
	config := cmd.ParseFlags()

	// If no specific action is requested, show help
	if config.Directory == "" && config.SearchQuery == "" && !config.ListFiles && !config.ShowStats && config.SQLQuery == "" {
		cmd.ShowHelp()
		return
	}

	// Create indexer
	indexer := indexer.NewIndexer(config.IndexPath, config.UseDB)

	// Create CLI
	cli := cmd.NewCLI(indexer)

	// Run the CLI
	if err := cli.Run(config); err != nil {
		log.Fatalf("Error: %v", err)
	}
}
