package models

import "time"

// FileInfo represents information about an indexed file
type FileInfo struct {
	Path                 string    `json:"path"`
	Filename             string    `json:"filename"`
	Checksum             string    `json:"checksum"`
	ModificationDateTime time.Time `json:"modification_datetime"`
	FileSize             int64     `json:"file_size"`
	IndexedAt            time.Time `json:"indexed_at"`
}

// Index represents the file index (for JSON compatibility)
type Index struct {
	Files    map[string]FileInfo `json:"files"`
	Indexed  time.Time           `json:"indexed"`
	RootPath string              `json:"root_path"`
}
