package indexer

import (
	"crypto/sha256"
	"encoding/hex"
	"io"
	"os"
)

// ChecksumFile computes the SHA256 checksum of a file
func ChecksumFile(path string) (string, error) {
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
