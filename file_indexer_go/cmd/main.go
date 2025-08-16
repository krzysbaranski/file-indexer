package cmd

import (
	"file_indexer_go/indexer"
)

func main() {
	// Default values for demonstration; these should be set via flags or config
	indexPath := "file_index.json"
	useDB := false
	idx := indexer.NewIndexer(indexPath, useDB)
	cli := NewCLI(idx)
	config := ParseFlags()
	if err := cli.Run(config); err != nil {
		panic(err)
	}
}
