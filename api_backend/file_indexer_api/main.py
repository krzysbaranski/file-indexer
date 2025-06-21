"""
Main FastAPI application for the File Indexer API.
"""

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .database import DatabaseService
from .routers import (
    duplicates_router,
    get_database_service,
    health_router,
    search_router,
    stats_router,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global database service instance
db_service: DatabaseService | None = None


def override_get_database_service() -> DatabaseService:
    """Override for the database service dependency."""
    global db_service
    if db_service is None:
        raise HTTPException(status_code=503, detail="Database service not available")
    return db_service


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    """Application lifespan manager."""
    global db_service

    # Get database path from environment or use default
    db_path = os.getenv("FILE_INDEXER_DB_PATH", "file_index.db")

    # Check if database exists
    if not Path(db_path).exists():
        logger.error(f"Database file not found: {db_path}")
        logger.info(
            "Please set the FILE_INDEXER_DB_PATH environment variable to the correct database path"
        )
        sys.exit(1)

    # Initialize database service
    try:
        db_service = DatabaseService(db_path)
        db_service.connect()
        logger.info(f"Connected to database: {db_path}")
        yield
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        sys.exit(1)
    finally:
        # Cleanup
        if db_service:
            db_service.disconnect()
            logger.info("Disconnected from database")


# Create FastAPI app
app = FastAPI(
    title="File Indexer API",
    description="REST API for querying file index database with search, duplicate detection, and visualization capabilities",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Override the dependency
app.dependency_overrides[get_database_service] = override_get_database_service

# Include routers
app.include_router(health_router)
app.include_router(search_router)
app.include_router(duplicates_router)
app.include_router(stats_router)


@app.exception_handler(Exception)
async def general_exception_handler(request: Any, exc: Exception) -> JSONResponse:
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500, content={"error": "Internal server error", "detail": str(exc)}
    )


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint with API information."""
    return {
        "message": "File Indexer API",
        "version": "0.1.0",
        "docs": "/docs",
        "redoc": "/redoc",
    }


def run_server() -> None:
    """Run the server (used by the CLI script)."""
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")

    uvicorn.run(
        "file_indexer_api.main:app", host=host, port=port, reload=False, access_log=True
    )


if __name__ == "__main__":
    run_server()
