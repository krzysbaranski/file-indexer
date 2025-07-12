package models

import "time"

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

// Index represents the file index (for JSON compatibility)
type Index struct {
	Files    map[string]FileInfo `json:"files"`
	Indexed  time.Time           `json:"indexed"`
	RootPath string              `json:"root_path"`
}