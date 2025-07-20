# Makefile for File Indexer Tool

BINARY_NAME=file-indexer
SOURCE_FILES=main.go

.PHONY: build clean test run-example help

# Default target
all: build

# Build the binary
build:
	@echo "Building $(BINARY_NAME)..."
	go build -o $(BINARY_NAME) $(SOURCE_FILES)
	@echo "Build complete!"

# Clean build artifacts
clean:
	@echo "Cleaning build artifacts..."
	rm -f $(BINARY_NAME)
	rm -f file_index.json
	rm -rf test_files
	@echo "Clean complete!"

# Run tests (if any)
test:
	@echo "Running tests..."
	go test ./...
	@echo "Tests complete!"

# Run the example script
run-example: build
	@echo "Running example..."
	./example.sh

# Show help
help:
	@echo "File Indexer Tool - Makefile"
	@echo "============================"
	@echo ""
	@echo "Available targets:"
	@echo "  build        - Build the binary"
	@echo "  clean        - Remove build artifacts and test files"
	@echo "  test         - Run tests"
	@echo "  run-example  - Build and run the example script"
	@echo "  help         - Show this help message"
	@echo ""
	@echo "Usage examples:"
	@echo "  make build"
	@echo "  make run-example"
	@echo "  make clean"

# Install the binary to /usr/local/bin (requires sudo)
install: build
	@echo "Installing $(BINARY_NAME) to /usr/local/bin..."
	sudo cp $(BINARY_NAME) /usr/local/bin/
	@echo "Installation complete!"

# Uninstall the binary
uninstall:
	@echo "Removing $(BINARY_NAME) from /usr/local/bin..."
	sudo rm -f /usr/local/bin/$(BINARY_NAME)
	@echo "Uninstallation complete!"