# File Indexer API

A REST API backend for querying DuckDB file index databases, providing search, duplicate detection, and visualization capabilities.

## Features

- **File Search**: Search files by filename patterns, paths, checksums, size ranges, and modification dates
- **Duplicate Detection**: Find and explore duplicate files grouped by checksum
- **Database Statistics**: Get comprehensive statistics about indexed files
- **Visualization Data**: Retrieve data for charts and graphs (file size distribution, extension statistics, modification timeline)
- **Health Monitoring**: Health check endpoints for monitoring
- **OpenAPI Documentation**: Automatic API documentation with Swagger UI

## Installation

### Using Poetry (Recommended)

```bash
cd api_backend
poetry install
```

### Using pip

```bash
cd api_backend
pip install -r requirements.txt
```

## Usage

### Environment Variables

- `FILE_INDEXER_DB_PATH`: Path to the DuckDB database file (required)
- `HOST`: Host to bind to (default: `0.0.0.0`)
- `PORT`: Port to listen on (default: `8000`)

### Running the API

#### Using Poetry

```bash
cd api_backend
export FILE_INDEXER_DB_PATH=/path/to/your/file_index.db
poetry run file-indexer-api
```

#### Using Python directly

```bash
cd api_backend
export FILE_INDEXER_DB_PATH=/path/to/your/file_index.db
python -m file_indexer_api.main
```

#### Using uvicorn directly

```bash
cd api_backend
export FILE_INDEXER_DB_PATH=/path/to/your/file_index.db
uvicorn file_indexer_api.main:app --host 0.0.0.0 --port 8000
```

### API Documentation

Once the server is running, you can access:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## API Endpoints

### Health Check

- `GET /health/` - Check API and database health

### File Search

- `POST /search/` - Search files with JSON request body
- `GET /search/` - Search files with query parameters

**Search Parameters:**
- `filename_pattern`: SQL LIKE pattern for filenames
- `path_pattern`: SQL LIKE pattern for file paths
- `checksum`: Exact checksum match
- `has_checksum`: Filter files with/without checksums
- `min_size`/`max_size`: File size range in bytes
- `modified_after`/`modified_before`: Date range filters
- `limit`: Results per page (1-10000, default: 100)
- `offset`: Pagination offset (default: 0)

### Duplicates

- `GET /duplicates/` - Find duplicate files
  - `min_group_size`: Minimum files per group (default: 2)

### Statistics

- `GET /stats/` - Get database statistics
- `GET /stats/visualization` - Get visualization data

## Examples

### Search for Python files

```bash
curl "http://localhost:8000/search/?filename_pattern=*.py&limit=10"
```

### Search for large files

```bash
curl "http://localhost:8000/search/?min_size=1000000&limit=5"
```

### Find duplicates

```bash
curl "http://localhost:8000/duplicates/"
```

### Get database statistics

```bash
curl "http://localhost:8000/stats/"
```

### Advanced search with POST

```bash
curl -X POST "http://localhost:8000/search/" \
  -H "Content-Type: application/json" \
  -d '{
    "filename_pattern": "%.pdf",
    "min_size": 100000,
    "max_size": 10000000,
    "limit": 50
  }'
```

## Response Models

### FileRecord

```json
{
  "path": "/home/user/documents",
  "filename": "example.pdf",
  "checksum": "abc123...",
  "modification_datetime": "2023-01-01T12:00:00",
  "file_size": 1048576,
  "indexed_at": "2023-01-01T13:00:00"
}
```

### SearchResponse

```json
{
  "files": [...],
  "total_count": 150,
  "has_more": true
}
```

### DuplicateGroup

```json
{
  "checksum": "abc123...",
  "file_size": 1048576,
  "file_count": 3,
  "files": [...]
}
```

## Development

### Running Tests

```bash
cd api_backend
poetry run pytest
```

### Code Formatting and Linting

```bash
cd api_backend
poetry run ruff check .
poetry run ruff format .
poetry run mypy .
```

### Adding Dependencies

```bash
cd api_backend
poetry add package_name
```

## Production Deployment

### Docker

Create a `Dockerfile`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml poetry.lock ./
RUN pip install poetry && poetry config virtualenvs.create false
RUN poetry install --no-dev

COPY file_indexer_api ./file_indexer_api

EXPOSE 8000

CMD ["python", "-m", "file_indexer_api.main"]
```

### Environment Configuration

For production, configure these environment variables:

- `FILE_INDEXER_DB_PATH`: Path to your database
- `HOST`: Usually `0.0.0.0`
- `PORT`: Your desired port
- Configure CORS origins in `main.py` for security

### Reverse Proxy

Example nginx configuration:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Architecture

The API is built with:

- **FastAPI**: Modern, fast web framework
- **DuckDB**: High-performance analytical database
- **Pydantic**: Data validation and serialization
- **Uvicorn**: ASGI server

### Project Structure

```
api_backend/
├── file_indexer_api/
│   ├── __init__.py
│   ├── main.py          # FastAPI application
│   ├── models.py        # Pydantic models
│   ├── database.py      # Database service layer
│   └── routers.py       # API route handlers
├── pyproject.toml       # Poetry configuration
└── README.md           # This file
```

## License

MIT License 