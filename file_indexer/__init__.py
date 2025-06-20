"""
File Indexer using DuckDB
A Python-based file indexing system that creates and maintains a DuckDB database
of files with their metadata, including checksums, modification dates, and file sizes.
"""

from .indexer import FileIndexer
from .utils import format_size

__version__ = "0.1.0"
__all__ = ["FileIndexer", "format_size"]
