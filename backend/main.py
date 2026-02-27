"""
FastAPI Backend for MyrientDL

Provides REST API for game archive browsing and downloading.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from pydantic import BaseModel
import os

from .database import get_db, DatabaseManager
from .models import (
    GameFileResponse,
    CollectionResponse,
    SearchRequest,
    DownloadRequest,
    StatsResponse,
    CrawlStatus,
)
from .services import CrawlService, DownloadService, SearchService

# Environment variables
DATABASE_URL = os.getenv("DATABASE_URL")
MYRIENT_BASE_URL = os.getenv("MYRIENT_BASE_URL", "https://myrient.erista.me")

app = FastAPI(
    title="MyrientDL API",
    description="Backend API for Myrient game archive downloader",
    version="0.1.0",
)

# CORS middleware for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js dev
        os.getenv("FRONTEND_URL", "*"),  # Production frontend
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check
@app.get("/")
async def root():
    return {
        "status": "ok",
        "service": "MyrientDL API",
        "version": "0.1.0",
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


# Collections
@app.get("/api/collections", response_model=List[CollectionResponse])
async def get_collections(db: DatabaseManager = Depends(get_db)):
    """Get all collections with game counts"""
    collections = await db.get_collections_with_stats()
    return collections


# Search
@app.post("/api/search", response_model=List[GameFileResponse])
async def search_games(
    request: SearchRequest,
    db: DatabaseManager = Depends(get_db),
):
    """Search for games with fuzzy matching"""
    search_service = SearchService(db)
    results = await search_service.search(
        query=request.query,
        console=request.console,
        collection=request.collection,
        limit=request.limit or 50,
    )
    return results


# Games
@app.get("/api/games", response_model=List[GameFileResponse])
async def list_games(
    console: Optional[str] = None,
    collection: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: DatabaseManager = Depends(get_db),
):
    """List games with optional filters"""
    games = await db.get_games(
        console=console,
        collection=collection,
        limit=limit,
        offset=offset,
    )
    return games


@app.get("/api/games/{game_id}", response_model=GameFileResponse)
async def get_game(game_id: int, db: DatabaseManager = Depends(get_db)):
    """Get a specific game by ID"""
    game = await db.get_game_by_id(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    return game


# Crawl
@app.post("/api/crawl/start")
async def start_crawl(
    background_tasks: BackgroundTasks,
    db: DatabaseManager = Depends(get_db),
):
    """Start crawling Myrient archive (background task)"""
    crawl_service = CrawlService(db)

    # Check if crawl is already running
    status = await crawl_service.get_status()
    if status.is_running:
        raise HTTPException(status_code=409, detail="Crawl already in progress")

    # Start crawl in background
    background_tasks.add_task(crawl_service.start_crawl)

    return {"status": "started", "message": "Crawl started in background"}


@app.get("/api/crawl/status", response_model=CrawlStatus)
async def get_crawl_status(db: DatabaseManager = Depends(get_db)):
    """Get current crawl status"""
    crawl_service = CrawlService(db)
    status = await crawl_service.get_status()
    return status


# Download
@app.post("/api/download")
async def queue_download(
    request: DownloadRequest,
    background_tasks: BackgroundTasks,
    db: DatabaseManager = Depends(get_db),
):
    """Queue games for download"""
    download_service = DownloadService(db)

    # Queue downloads
    queued = await download_service.queue_downloads(request.game_ids)

    # Start download worker in background if not already running
    if not download_service.is_running():
        background_tasks.add_task(download_service.start_worker)

    return {
        "status": "queued",
        "queued_count": len(queued),
        "game_ids": queued,
    }


@app.get("/api/download/status")
async def get_download_status(db: DatabaseManager = Depends(get_db)):
    """Get download queue status"""
    download_service = DownloadService(db)
    status = await download_service.get_status()
    return status


# Stats
@app.get("/api/stats", response_model=StatsResponse)
async def get_stats(db: DatabaseManager = Depends(get_db)):
    """Get overall statistics"""
    stats = await db.get_stats()
    return stats


# Consoles
@app.get("/api/consoles", response_model=List[str])
async def get_consoles(db: DatabaseManager = Depends(get_db)):
    """Get list of all consoles"""
    consoles = await db.get_consoles()
    return consoles


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
