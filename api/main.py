"""
FastAPI Backend for MyrientDL

Provides REST API for game archive browsing and downloading.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from pydantic import BaseModel
from contextlib import asynccontextmanager
import os
import traceback
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from database import get_db, DatabaseManager, init_db, close_db
from models import (
    GameFileResponse,
    CollectionResponse,
    SearchRequest,
    DownloadRequest,
    StatsResponse,
    CrawlStatus,
)
from services import CrawlService, DownloadService, SearchService

# Environment variables
DATABASE_URL = os.getenv("DATABASE_URL")
MYRIENT_BASE_URL = os.getenv("MYRIENT_BASE_URL", "https://myrient.erista.me")


# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        logger.error(traceback.format_exc())
    yield
    # Shutdown
    await close_db()


app = FastAPI(
    title="MyrientDL API",
    description="Backend API for Myrient game archive downloader",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware for Next.js frontend
frontend_url = os.getenv("FRONTEND_URL", "")
allowed_origins = [
    "http://localhost:3000",  # Next.js dev
    "https://myrient-dl.vercel.app",  # Your Vercel deployment
]

if frontend_url:
    allowed_origins.append(frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
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
    db = get_db()
    return {
        "status": "healthy",
        "database": "connected" if db else "not_initialized"
    }


# Collections
@app.get("/api/collections")
async def get_collections(db: DatabaseManager = Depends(get_db)):
    """Get all collections with game counts"""
    try:
        collections = await db.get_collections_with_stats()
        return collections
    except Exception as e:
        logger.error(f"Error in get_collections: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# Search
@app.post("/api/search")
async def search_games(
    request: SearchRequest,
    db: DatabaseManager = Depends(get_db),
):
    """Search for games with fuzzy matching"""
    try:
        search_service = SearchService(db)
        results = await search_service.search(
            query=request.query,
            console=request.console,
            collection=request.collection,
            limit=request.limit or 50,
        )
        return results
    except Exception as e:
        logger.error(f"Error in search_games: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# Games
@app.get("/api/games")
async def list_games(
    console: Optional[str] = None,
    collection: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: DatabaseManager = Depends(get_db),
):
    """List games with optional filters"""
    try:
        games = await db.get_games(
            console=console,
            collection=collection,
            limit=limit,
            offset=offset,
        )
        return games
    except Exception as e:
        logger.error(f"Error in list_games: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/games/{game_id}")
async def get_game(game_id: int, db: DatabaseManager = Depends(get_db)):
    """Get a specific game by ID"""
    try:
        game = await db.get_game_by_id(game_id)
        if not game:
            raise HTTPException(status_code=404, detail="Game not found")
        return game
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_game: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# Crawl
@app.post("/api/crawl/start")
async def start_crawl(
    background_tasks: BackgroundTasks,
    db: DatabaseManager = Depends(get_db),
):
    """Start crawling Myrient archive (background task)"""
    try:
        crawl_service = CrawlService(db)

        # Check if crawl is already running
        status = await crawl_service.get_status()
        if status["is_running"]:  # status is a dict
            raise HTTPException(status_code=409, detail="Crawl already in progress")

        # Start crawl in background
        background_tasks.add_task(crawl_service.start_crawl)

        return {"status": "started", "message": "Crawl started in background"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in start_crawl: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/crawl/status")
async def get_crawl_status(db: DatabaseManager = Depends(get_db)):
    """Get current crawl status"""
    try:
        crawl_service = CrawlService(db)
        status = await crawl_service.get_status()
        return status
    except Exception as e:
        logger.error(f"Error in get_crawl_status: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# Download
@app.post("/api/download")
async def queue_download(
    request: DownloadRequest,
    background_tasks: BackgroundTasks,
    db: DatabaseManager = Depends(get_db),
):
    """Queue games for download"""
    try:
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
    except Exception as e:
        logger.error(f"Error in queue_download: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/download/status")
async def get_download_status(db: DatabaseManager = Depends(get_db)):
    """Get download queue status"""
    try:
        download_service = DownloadService(db)
        status = await download_service.get_status()
        return status
    except Exception as e:
        logger.error(f"Error in get_download_status: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# Stats
@app.get("/api/stats")
async def get_stats(db: DatabaseManager = Depends(get_db)):
    """Get overall statistics"""
    try:
        stats = await db.get_stats()
        return stats
    except Exception as e:
        logger.error(f"Error in get_stats: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# Consoles
@app.get("/api/consoles")
async def get_consoles(db: DatabaseManager = Depends(get_db)):
    """Get list of all consoles"""
    try:
        consoles = await db.get_consoles()
        return consoles
    except Exception as e:
        logger.error(f"Error in get_consoles: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
