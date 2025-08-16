package main

import (
	"file_indexer_go/checksum"
	"fmt"
	"os"
	"path/filepath"
)

func main() {
	if len(os.Args) < 2 {
		fmt.Println("Usage: checksum <directory>")
		os.Exit(1)
	}
	dir := os.Args[1]
	var files []string
	filepath.Walk(dir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		if !info.IsDir() {
			files = append(files, path)
		}
		return nil
	})

	results := checksum.FilesParallel(files, 8) // 8 workers
	for _, res := range results {
		if res.Err != nil {
			fmt.Printf("%s: error: %v\n", res.Path, res.Err)
		} else {
			fmt.Printf("%s: %s\n", res.Path, res.Checksum)
		}
	}
}
