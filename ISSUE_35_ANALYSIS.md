# Issue #35 Analysis: DuckDB TransactionException

## Problem Description

The error occurs when running the `--calculate-duplicates` command:

```
duckdb.duckdb.TransactionException: TransactionContext Error: Failed to commit: Invalid node type for ARTOperator::Insert
```

Additional error message: `node without metadata in ARTOperator::Insert`

## Root Cause Analysis

### 1. Database Corruption
The error "Invalid node type for ARTOperator::Insert" and "node without metadata in ARTOperator::Insert" indicates **database corruption** in DuckDB. This is a known issue that can occur when:

- The database file becomes corrupted due to system crashes, power failures, or disk issues
- Concurrent access to the database file
- Memory pressure causing incomplete writes
- DuckDB version compatibility issues

### 2. Transaction Context Issues
The error occurs during a `COMMIT` operation in the `_calculate_checksums_for_files` method, specifically when updating file records with checksums. The transaction context becomes invalid, likely due to:

- Corrupted internal DuckDB structures
- Inconsistent state between the transaction log and the main database file
- Memory corruption during bulk operations

### 3. Specific Trigger Conditions
The issue is more likely to occur when:
- Processing large numbers of files (2,990,760 files in the reported case)
- Using parallel processing with multiple workers
- Operating on network storage (NAS in this case)
- Running on systems with memory constraints

## Technical Details

### Error Location
```python
# In _calculate_checksums_for_files method (line 1690)
self.conn.execute("COMMIT")  # <-- Error occurs here
```

### Affected Operations
- `--calculate-duplicates` command
- `calculate_checksums_for_duplicates()` method
- Bulk UPDATE operations on the `files` table

### Database Schema
The `files` table structure:
```sql
CREATE TABLE files (
    path VARCHAR NOT NULL,
    filename VARCHAR NOT NULL,
    checksum VARCHAR,  -- Nullable
    modification_datetime TIMESTAMP NOT NULL,
    file_size BIGINT NOT NULL,
    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (path, filename)
);
```

## Impact Assessment

### Severity: HIGH
- **Data Loss Risk**: Database corruption can lead to data loss
- **Functionality Impact**: Critical feature (duplicate detection) becomes unusable
- **User Experience**: Process fails after significant processing time
- **Recurrence**: Issue persists even after database recreation

### Affected Users
- Users processing large file collections
- Users on network storage systems
- Users with memory-constrained systems
- Users running parallel processing

## Proposed Solutions

### 1. Immediate Fix: Enhanced Error Handling and Recovery

**Add database integrity checks and recovery mechanisms:**

```python
def _safe_database_operation(self, operation_func, *args, **kwargs):
    """Execute database operations with corruption detection and recovery."""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            return operation_func(*args, **kwargs)
        except duckdb.TransactionException as e:
            if "Invalid node type" in str(e) or "node without metadata" in str(e):
                print(f"Database corruption detected (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    self._attempt_database_recovery()
                    continue
                else:
                    raise DatabaseCorruptionError("Database corruption detected and recovery failed")
            raise
```

### 2. Database Recovery Mechanisms

**Add methods to detect and recover from corruption:**

```python
def _attempt_database_recovery(self):
    """Attempt to recover from database corruption."""
    try:
        # Try to create a backup of current state
        backup_path = f"{self.db_path}.backup_{int(time.time())}"
        self.conn.execute(f"EXPORT DATABASE '{backup_path}'")
        
        # Recreate database with clean state
        self._recreate_database()
        
    except Exception as e:
        print(f"Recovery failed: {e}")
        raise DatabaseCorruptionError("Unable to recover from database corruption")

def _recreate_database(self):
    """Recreate database with clean state."""
    # Implementation to recreate database structure
    pass
```

### 3. Transaction Safety Improvements

**Implement safer transaction handling:**

```python
def _calculate_checksums_for_files_safe(self, file_paths: list[str]) -> int:
    """Safe version with better transaction handling."""
    if not file_paths:
        return 0
    
    # Process in smaller chunks to reduce transaction size
    chunk_size = 100  # Smaller chunks for safety
    total_updated = 0
    
    for i in range(0, len(file_paths), chunk_size):
        chunk = file_paths[i:i + chunk_size]
        updated = self._process_checksum_chunk(chunk)
        total_updated += updated
    
    return total_updated

def _process_checksum_chunk(self, file_paths: list[str]) -> int:
    """Process a small chunk of files with individual transaction."""
    # Implementation with individual transactions per chunk
    pass
```

### 4. Configuration Improvements

**Add configuration options for corruption prevention:**

```python
# In FileIndexer.__init__
self.corruption_safe_mode = corruption_safe_mode  # New parameter
self.transaction_chunk_size = transaction_chunk_size  # New parameter
```

### 5. Monitoring and Diagnostics

**Add corruption detection and reporting:**

```python
def check_database_integrity(self) -> bool:
    """Check database integrity and return True if healthy."""
    try:
        # Run integrity checks
        result = self.conn.execute("PRAGMA integrity_check").fetchone()
        return result[0] == "ok"
    except Exception:
        return False

def get_database_stats(self) -> dict:
    """Get detailed database statistics including corruption indicators."""
    # Implementation to gather database health metrics
    pass
```

## Implementation Plan

### Phase 1: Immediate Fixes (High Priority)
1. Add enhanced error handling with corruption detection
2. Implement transaction chunking for large operations
3. Add database integrity checks
4. Create recovery mechanisms

### Phase 2: Prevention (Medium Priority)
1. Add configuration options for safe mode
2. Implement automatic backup before large operations
3. Add monitoring and diagnostics
4. Improve transaction isolation

### Phase 3: Long-term Improvements (Low Priority)
1. Consider alternative database backends
2. Implement distributed processing options
3. Add comprehensive testing for corruption scenarios

## Testing Strategy

### Corruption Simulation
- Create corrupted database files
- Test recovery mechanisms
- Verify data integrity after recovery

### Stress Testing
- Large file collections (millions of files)
- Memory-constrained environments
- Network storage scenarios
- Concurrent access patterns

### Regression Testing
- Ensure existing functionality remains intact
- Test performance impact of safety measures
- Verify backward compatibility

## Conclusion

This is a **database corruption issue** that requires immediate attention due to the risk of data loss and functionality impact. The proposed solutions focus on:

1. **Detection**: Identify corruption early
2. **Recovery**: Provide mechanisms to recover from corruption
3. **Prevention**: Reduce the likelihood of corruption
4. **Monitoring**: Track database health

The implementation should prioritize user data safety while maintaining performance and functionality.