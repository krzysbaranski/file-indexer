# File Indexer API Integration Guide

This guide explains how to use the new API backend subproject with your existing file indexer.

## Overview

The `api_backend` subproject provides a REST API for querying your DuckDB file index database. It enables:

- **File Search**: Advanced search capabilities through HTTP endpoints
- **Duplicate Exploration**: Find and analyze duplicate files via API
- **Visualization Data**: Export data for charts, graphs, and analytics
- **Database Statistics**: Get comprehensive stats about your indexed files
- **Frontend Integration**: Perfect backend for web applications

## Quick Start

### 1. Index Your Files (Using Main Project)

First, create a file index using the main file indexer:

```bash
# Index a directory with two-phase indexing (recommended)
python -m file_indexer --two-phase /path/to/your/files --db my_files.db

# Or use traditional indexing
python -m file_indexer --scan /path/to/your/files --db my_files.db
```

### 2. Install API Backend Dependencies

```bash
cd api_backend

# Using Poetry (recommended)
poetry install
```

### 3. Start the API Server

```bash
# Set the database path
export FILE_INDEXER_DB_PATH=/path/to/your/my_files.db

# Start the server
cd api_backend
poetry run file-indexer-api

# Or using uvicorn directly
uvicorn file_indexer_api.main:app --host 0.0.0.0 --port 8000
```

### 4. Access the API

- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health/
- **Search Files**: http://localhost:8000/search/
- **Find Duplicates**: http://localhost:8000/duplicates/
- **Get Statistics**: http://localhost:8000/stats/

## Integration Examples

### Basic File Search

```bash
# Search for Python files
curl "http://localhost:8000/search/?filename_pattern=%.py&limit=10"

# Search for large files (>10MB)
curl "http://localhost:8000/search/?min_size=10485760"

# Search files in specific directory
curl "http://localhost:8000/search/?path_pattern=/home/user/Documents%"
```

### Advanced Search with POST

```bash
curl -X POST "http://localhost:8000/search/" \
  -H "Content-Type: application/json" \
  -d '{
    "filename_pattern": "%.pdf",
    "min_size": 100000,
    "max_size": 10000000,
    "has_checksum": true,
    "limit": 50
  }'
```

### Find Duplicates

```bash
# Find all duplicate files
curl "http://localhost:8000/duplicates/"

# Find groups with at least 3 duplicates
curl "http://localhost:8000/duplicates/?min_group_size=3"
```

### Get Database Statistics

```bash
# Basic statistics
curl "http://localhost:8000/stats/"

# Data for visualization/charts
curl "http://localhost:8000/stats/visualization"
```

## Frontend Integration

The API is designed to be consumed by frontend applications. Here's an example React/JavaScript integration:

### JavaScript Client Example

```javascript
class FileIndexerAPI {
  constructor(baseUrl = 'http://localhost:8000') {
    this.baseUrl = baseUrl;
  }

  async searchFiles(params) {
    const queryString = new URLSearchParams(params).toString();
    const response = await fetch(`${this.baseUrl}/search/?${queryString}`);
    return await response.json();
  }

  async findDuplicates(minGroupSize = 2) {
    const response = await fetch(`${this.baseUrl}/duplicates/?min_group_size=${minGroupSize}`);
    return await response.json();
  }

  async getStats() {
    const response = await fetch(`${this.baseUrl}/stats/`);
    return await response.json();
  }

  async getVisualizationData() {
    const response = await fetch(`${this.baseUrl}/stats/visualization`);
    return await response.json();
  }
}

// Usage
const api = new FileIndexerAPI();

// Search for images
const images = await api.searchFiles({
  filename_pattern: '%.jpg',
  min_size: 50000,
  limit: 20
});

// Find duplicates
const duplicates = await api.findDuplicates(2);

// Get database stats
const stats = await api.getStats();
```

### Python Client Example

See `api_backend/examples/api_client_demo.py` for a comprehensive Python client example.

## Deployment Options

### Option 1: Docker

```bash
cd api_backend

# Build and run with Docker
docker build -t file-indexer-api .
docker run -p 8000:8000 -v /path/to/your/database:/data/file_index.db:ro file-indexer-api
```

### Option 2: Docker Compose

```bash
cd api_backend

# Create data directory and copy your database
mkdir -p data
cp /path/to/your/file_index.db data/

# Start with docker-compose
docker-compose up -d
```

### Option 3: Production Server

```bash
# Install dependencies
cd api_backend
poetry install --no-dev

# Run with gunicorn for production
pip install gunicorn
gunicorn file_indexer_api.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## Use Cases

### 1. Web File Explorer

Build a web interface to:
- Browse indexed files with search and filtering
- View file details, sizes, and modification dates
- Navigate directory structures
- Show file statistics and charts

### 2. Duplicate File Manager

Create a duplicate management tool to:
- Identify and list duplicate files
- Show file groups with same checksums
- Provide tools to delete or move duplicates
- Calculate space savings from deduplication

### 3. Storage Analytics Dashboard

Build analytics dashboards to:
- Visualize file size distributions
- Show file type breakdowns
- Track file modification patterns over time
- Monitor storage growth and usage patterns

### 4. File Search Application

Develop advanced search tools to:
- Search by multiple criteria simultaneously
- Save and reuse search queries
- Export search results to various formats
- Integrate with file management workflows

## API Endpoints Reference

### Health Check
- `GET /health/` - Check API and database status

### File Search
- `GET /search/` - Search with query parameters
- `POST /search/` - Advanced search with JSON body

### Duplicates
- `GET /duplicates/` - Find duplicate file groups

### Statistics
- `GET /stats/` - Get database statistics
- `GET /stats/visualization` - Get visualization data

### Parameters

**Search Parameters:**
- `filename_pattern`: SQL LIKE pattern (e.g., `%.pdf`, `photo*`)
- `path_pattern`: Path pattern (e.g., `/home/user/%`)
- `checksum`: Exact checksum match
- `has_checksum`: `true`/`false` to filter by checksum presence
- `min_size`/`max_size`: File size range in bytes
- `modified_after`/`modified_before`: ISO datetime strings
- `limit`: Max results (1-10000, default: 100)
- `offset`: Pagination offset (default: 0)

## Performance Considerations

1. **Database Size**: Large databases may require longer query times
2. **Pagination**: Use `limit` and `offset` for large result sets
3. **Indexing**: Ensure your database has been properly indexed
4. **Caching**: Consider adding caching for frequently accessed data
5. **Read-Only**: The API opens the database in read-only mode for safety

## Security Notes

- The API currently allows CORS from all origins (`*`) - configure this for production
- No authentication is implemented - add auth middleware if needed
- Database is opened read-only to prevent accidental modifications
- Consider running behind a reverse proxy (nginx, Apache) in production

## Troubleshooting

### Common Issues

1. **Database not found**: Ensure `FILE_INDEXER_DB_PATH` environment variable is set correctly
2. **Connection refused**: Make sure the API server is running on the expected port
3. **Empty results**: Verify your search patterns and database content
4. **Permission errors**: Check file permissions for the database file

### Debugging

Enable debug logging:

```bash
export LOG_LEVEL=DEBUG
python -m file_indexer_api.main
```

Check the API health:

```bash
curl http://localhost:8000/health/
```

## Next Steps

1. **Index your files** using the main file indexer
2. **Start the API server** and test with the provided examples
3. **Build your frontend** using the API endpoints
4. **Deploy to production** using Docker or your preferred method
5. **Monitor and optimize** based on your usage patterns

For more detailed examples and advanced usage, see the files in `api_backend/examples/`.

## Architecture Diagram

```
┌─────────────────┐    HTTP/JSON    ┌──────────────────┐    SQL     ┌─────────────┐
│   Frontend      │◄──────────────► │   FastAPI        │◄──────────► │   DuckDB    │
│   (React/Vue/   │                 │   API Server     │             │   Database  │
│    Angular)     │                 │                  │             │             │
└─────────────────┘                 └──────────────────┘             └─────────────┘
                                             │
                                             ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                          File Indexer CLI                                           │
│  ┌─────────────────────────────────────────────────────────────────────────────────┤
│  │  python -m file_indexer --two-phase /path/to/files --db database.db           │
│  └─────────────────────────────────────────────────────────────────────────────────┤
└─────────────────────────────────────────────────────────────────────────────────────┘
```

This integration allows you to:
1. Use the powerful CLI tool to index your files
2. Query and explore the data through a modern REST API
3. Build rich frontend applications on top of the indexed data 
