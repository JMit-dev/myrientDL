"""
Backend Services

Business logic for crawling, downloading, and searching.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
import asyncio

from .database import DatabaseManager


class CrawlService:
    """Service for managing crawl operations"""

    def __init__(self, db: DatabaseManager):
        self.db = db
        self._is_running = False
        self._games_found = 0
        self._current_url = None
        self._last_crawl = None

    async def start_crawl(self):
        """Start crawling Myrient (background task)"""
        # TODO: Implement actual crawling logic using myrientDL crawler
        self._is_running = True
        self._games_found = 0
        self._current_url = "https://myrient.erista.me"

        try:
            # Placeholder - integrate with actual crawler
            await asyncio.sleep(1)
            self._last_crawl = datetime.now()
        finally:
            self._is_running = False

    async def get_status(self) -> Dict[str, Any]:
        """Get current crawl status"""
        return {
            "is_running": self._is_running,
            "games_found": self._games_found,
            "last_crawl": self._last_crawl,
            "current_url": self._current_url,
            "progress_percentage": 0.0 if self._is_running else 100.0,
        }


class DownloadService:
    """Service for managing downloads"""

    def __init__(self, db: DatabaseManager):
        self.db = db
        self._is_running = False
        self._queue: List[int] = []

    async def queue_downloads(self, game_ids: List[int]) -> List[int]:
        """Queue games for download"""
        # TODO: Update game status to pending in database
        self._queue.extend(game_ids)
        return game_ids

    async def start_worker(self):
        """Start download worker (background task)"""
        self._is_running = True

        try:
            # TODO: Implement actual download logic
            while self._queue:
                game_id = self._queue.pop(0)
                await asyncio.sleep(0.1)
        finally:
            self._is_running = False

    def is_running(self) -> bool:
        """Check if download worker is running"""
        return self._is_running

    async def get_status(self) -> Dict[str, Any]:
        """Get download queue status"""
        return {
            "is_running": self._is_running,
            "queue_length": len(self._queue),
            "active_downloads": 0,
        }


class SearchService:
    """Service for searching games"""

    def __init__(self, db: DatabaseManager):
        self.db = db

    async def search(
        self,
        query: str,
        console: Optional[str] = None,
        collection: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict]:
        """Search for games with fuzzy matching"""
        # TODO: Implement fuzzy search using existing search module
        # For now, basic SQL LIKE search
        games = await self.db.get_games(
            console=console,
            collection=collection,
            limit=limit,
        )

        # Filter by query (case-insensitive)
        if query:
            query_lower = query.lower()
            games = [g for g in games if query_lower in g['name'].lower()]

        return games[:limit]
