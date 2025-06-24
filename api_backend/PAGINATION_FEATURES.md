# API Pagination and Filtering Features

## Overview
The File Indexer API has been enhanced with comprehensive pagination and filtering capabilities, particularly for the duplicates endpoint.

## New Features

### 1. Duplicates API Enhancements

#### Enhanced Models
- **`DuplicatesRequest`**: New request model for filtering and pagination
- **`DuplicateGroup`**: Now includes `wasted_space` field
- **`DuplicatesResponse`**: Added `total_wasted_space` and `has_more` fields

#### Pagination Parameters
- `limit`: Maximum number of duplicate groups to return (1-1000, default: 100)
- `offset`: Number of groups to skip for pagination (default: 0)

#### File Size Filtering
- `min_file_size`: Minimum file size in bytes (optional)
- `max_file_size`: Maximum file size in bytes (optional)
- `min_group_size`: Minimum number of files in a group (default: 2)

### 2. API Endpoints

#### GET /duplicates/
Query parameters for simple requests:
```
GET /duplicates/?min_group_size=3&min_file_size=1048576&max_file_size=104857600&limit=10&offset=0
```

#### POST /duplicates/
JSON body for complex requests:
```json
{
  "min_group_size": 3,
  "min_file_size": 1048576,
  "max_file_size": 104857600,
  "limit": 10,
  "offset": 0
}
```

### 3. Response Format
```json
{
  "duplicate_groups": [...],
  "total_groups": 150,
  "total_duplicate_files": 420,
  "total_wasted_space": 2147483648,
  "has_more": true
}
```

### 4. Optimized Database Queries

#### Performance Improvements
- Self-join approach instead of subqueries
- Efficient pagination with LIMIT/OFFSET
- Size filtering at query level
- Wasted space calculation included

#### Example Optimized Query
```sql
WITH duplicate_checksums AS (
    SELECT checksum, file_size, COUNT(*) as file_count
    FROM files
    WHERE checksum IS NOT NULL 
    AND file_size >= ? AND file_size <= ?
    GROUP BY checksum, file_size
    HAVING COUNT(*) >= ?
    ORDER BY COUNT(*) DESC, file_size DESC
    LIMIT ? OFFSET ?
)
SELECT f.*, dc.file_count
FROM files f
JOIN duplicate_checksums dc ON f.checksum = dc.checksum 
ORDER BY dc.file_count DESC, f.checksum, f.path, f.filename
```

### 5. Client Examples

#### Python Client
```python
# Basic usage
duplicates = client.find_duplicates(
    min_file_size=1024*1024,  # 1MB
    limit=10
)

# Advanced usage with POST
request = {
    "min_group_size": 3,
    "min_file_size": 10*1024*1024,  # 10MB
    "max_file_size": 100*1024*1024,  # 100MB
    "limit": 5,
    "offset": 0
}
duplicates = client.find_duplicates_advanced(request)
```

#### cURL Examples
```bash
# GET request
curl "http://localhost:8000/duplicates/?min_file_size=1048576&limit=5"

# POST request
curl -X POST "http://localhost:8000/duplicates/" \
  -H "Content-Type: application/json" \
  -d '{"min_group_size": 3, "min_file_size": 1048576, "limit": 5}'
```

### 6. Use Cases

#### Large Files Only
Find duplicates of files larger than 10MB:
```json
{
  "min_file_size": 10485760,
  "limit": 20
}
```

#### Groups With Many Duplicates
Find groups with 5+ duplicate files:
```json
{
  "min_group_size": 5,
  "limit": 10
}
```

#### Paginated Results
Browse through duplicate groups:
```json
{
  "limit": 10,
  "offset": 20
}
```

### 7. Performance Benefits

- **Faster queries**: Self-join approach is more efficient than subqueries
- **Memory efficient**: Pagination prevents loading all results at once  
- **Targeted filtering**: Size filters reduce dataset early in query
- **Wasted space calculation**: Shows immediate impact of duplicates

### 8. Backward Compatibility

The existing `/duplicates/` GET endpoint without parameters continues to work as before, returning the first 100 duplicate groups with default settings.

## Testing

The enhanced API has been tested with:
- Unit tests for both GET and POST endpoints
- Parameter validation tests
- Mock database service integration
- Example client demonstrations

All tests pass and the API maintains backward compatibility while providing powerful new filtering and pagination capabilities. 