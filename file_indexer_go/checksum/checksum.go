package checksum

import (
	"crypto/sha256"
	"encoding/hex"
	"io"
	"os"
	"sync"
)

// Result holds the checksum result for a file
type Result struct {
	Path     string
	Checksum string
	Err      error
}

// File computes the SHA256 checksum of a file
func File(path string) (string, error) {
	file, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer file.Close()

	hash := sha256.New()
	if _, err := io.Copy(hash, file); err != nil {
		return "", err
	}
	return hex.EncodeToString(hash.Sum(nil)), nil
}

// FilesParallel computes checksums for multiple files using goroutines
func FilesParallel(paths []string, workerCount int) []Result {
	results := make([]Result, 0, len(paths))
	jobs := make(chan string, len(paths))
	out := make(chan Result, len(paths))
	var wg sync.WaitGroup

	for i := 0; i < workerCount; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for path := range jobs {
				checksum, err := File(path)
				out <- Result{Path: path, Checksum: checksum, Err: err}
			}
		}()
	}

	for _, path := range paths {
		jobs <- path
	}
	close(jobs)

	go func() {
		wg.Wait()
		close(out)
	}()

	for res := range out {
		results = append(results, res)
	}

	return results
}
