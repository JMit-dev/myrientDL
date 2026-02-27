"""
Backend Services

Business logic for crawling, downloading, and searching using myrientDL.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
import asyncio

from database import DatabaseManager
from myrientDL.crawler import MyrientCrawler
from myrientDL.downloader import DownloadManager
from myrientDL.search import GameSearch
from myrientDL.config import MyrientConfig


class CrawlService:
    """Service for managing crawl operations"""

    def __init__(self, db: DatabaseManager):
        self.db = db
        self._is_running = False
        self._games_found = 0
        self._current_url = None
        self._last_crawl = None

    async def start_crawl(self):
        """Start crawling Myrient"""
        self._is_running = True
        self._games_found = 0
        self._current_url = "https://myrient.erista.me"

        try:
            # Create crawler with myrientDL's actual crawler
            crawler = MyrientCrawler(self.db.db)

            # Crawl the entire site
            await crawler.crawl_all()

            # Update stats
            games = await self.db.db.get_all_games()
            self._games_found = len(games)
            self._last_crawl = datetime.now()

        except Exception as e:
            print(f"Crawl error: {e}")
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
        self._download_manager: Optional[DownloadManager] = None

    async def queue_downloads(self, game_ids: List[int]) -> List[int]:
        """Queue games for download"""
        # Mark games as pending in database
        for game_id in game_ids:
            game = await self.db.db.get_game(game_id)
            if game:
                await self.db.db.update_game_status(game_id, "pending")

        self._queue.extend(game_ids)
        return game_ids

    async def start_worker(self):
        """Start download worker (background task)"""
        self._is_running = True

        try:
            # Create download manager with default config
            config = MyrientConfig()
            self._download_manager = DownloadManager(
                config=config,
                database=self.db.db
            )

            # Process queue
            while self._queue:
                game_id = self._queue.pop(0)
                game = await self.db.db.get_game(game_id)

                if game:
                    await self._download_manager.download_game(game)

        except Exception as e:
            print(f"Download error: {e}")
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
            "active_downloads": 1 if self._is_running and self._queue else 0,
        }


class SearchService:
    """Service for searching games"""

    def __init__(self, db: DatabaseManager):
        self.db = db
        self.search = GameSearch(db.db)

    async def search(
        self,
        query: str,
        console: Optional[str] = None,
        collection: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict]:
        """Search for games with fuzzy matching"""
        # Use myrientDL's actual search
        results = await self.search.search(
            query=query,
            console=console,
            limit=limit
        )

        # Filter by collection if specified
        if collection:
            results = [r for r in results if r.game.collection.value == collection]

        # Convert to dicts
        return [self.db._game_to_dict(r.game) for r in results]
