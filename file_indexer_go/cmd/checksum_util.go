package cmd

import (
	"file_indexer_go/checksum"
	"fmt"
	"os"
	"path/filepath"
)

// ChecksumDirectory computes checksums for all files in a directory using parallel workers
func ChecksumDirectory(dir string, workers int) {
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

	results := checksum.FilesParallel(files, workers)
	for _, res := range results {
		if res.Err != nil {
			fmt.Printf("%s: error: %v\n", res.Path, res.Err)
		} else {
			fmt.Printf("%s: %s\n", res.Path, res.Checksum)
		}
	}
}
