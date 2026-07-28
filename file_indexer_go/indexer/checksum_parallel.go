package indexer

import (
	"sync"
)

// ChecksumResult holds the result for a file
type ChecksumResult struct {
	Path     string
	Checksum string
	Err      error
}

// ChecksumFilesParallel computes checksums for multiple files using goroutines
func ChecksumFilesParallel(paths []string, workerCount int) []ChecksumResult {
	results := make([]ChecksumResult, 0, len(paths))
	jobs := make(chan string, len(paths))
	out := make(chan ChecksumResult, len(paths))
	var wg sync.WaitGroup

	// Start workers
	for i := 0; i < workerCount; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for path := range jobs {
				checksum, err := ChecksumFile(path)
				out <- ChecksumResult{Path: path, Checksum: checksum, Err: err}
			}
		}()
	}

	// Send jobs
	for _, path := range paths {
		jobs <- path
	}
	close(jobs)

	// Wait for workers
	go func() {
		wg.Wait()
		close(out)
	}()

	// Collect results
	for res := range out {
		results = append(results, res)
	}

	return results
}
