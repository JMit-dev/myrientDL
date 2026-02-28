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

    # Class variables to share state across all instances
    _is_running = False
    _games_found = 0
    _current_url = None
    _last_crawl = None

    def __init__(self, db: DatabaseManager):
        self.db = db

    async def start_crawl(self):
        """Start crawling Myrient"""
        CrawlService._is_running = True
        CrawlService._games_found = 0
        CrawlService._current_url = "https://myrient.erista.me"

        try:
            # Create config with the database
            config = MyrientConfig(database_path=self.db.db_path)

            # Create crawler with myrientDL's actual crawler
            async with MyrientCrawler(config) as crawler:
                # Crawl from root directory with unlimited depth (it's an async generator)
                async for game in crawler.crawl_directory("https://myrient.erista.me", max_depth=999):
                    CrawlService._games_found += 1
                    # Games are automatically added to the database by the crawler

            CrawlService._last_crawl = datetime.now()

        except Exception as e:
            import traceback
            print(f"Crawl error: {e}")
            print(traceback.format_exc())
        finally:
            CrawlService._is_running = False

    async def get_status(self) -> Dict[str, Any]:
        """Get current crawl status"""
        return {
            "is_running": CrawlService._is_running,
            "games_found": CrawlService._games_found,
            "last_crawl": CrawlService._last_crawl,
            "current_url": CrawlService._current_url,
            "progress_percentage": 0.0 if CrawlService._is_running else 100.0,
        }


class DownloadService:
    """Service for managing downloads"""

    # Class variables to share state across all instances
    _is_running = False
    _queue: List[int] = []
    _download_manager: Optional[DownloadManager] = None

    def __init__(self, db: DatabaseManager):
        self.db = db

    async def queue_downloads(self, game_ids: List[int]) -> List[int]:
        """Queue games for download"""
        # Mark games as pending in database
        for game_id in game_ids:
            game = await self.db.db.get_game_file(game_id)
            if game:
                await self.db.db.update_game_file(game_id, status="pending")

        DownloadService._queue.extend(game_ids)
        return game_ids

    async def start_worker(self):
        """Start download worker (background task)"""
        DownloadService._is_running = True

        try:
            # Create download manager with default config
            config = MyrientConfig()
            DownloadService._download_manager = DownloadManager(
                config=config,
                database=self.db.db
            )

            # Process queue
            while DownloadService._queue:
                game_id = DownloadService._queue.pop(0)
                game = await self.db.db.get_game_file(game_id)

                if game:
                    await DownloadService._download_manager.download_game(game)

        except Exception as e:
            print(f"Download error: {e}")
        finally:
            DownloadService._is_running = False

    def is_running(self) -> bool:
        """Check if download worker is running"""
        return DownloadService._is_running

    async def get_status(self) -> Dict[str, Any]:
        """Get download queue status"""
        return {
            "is_running": DownloadService._is_running,
            "queue_length": len(DownloadService._queue),
            "active_downloads": 1 if DownloadService._is_running and DownloadService._queue else 0,
        }


class SearchService:
    """Service for searching games"""

    def __init__(self, db: DatabaseManager):
        self.db = db
        self.game_search = GameSearch(db.db)

    async def search(
        self,
        query: str,
        console: Optional[str] = None,
        collection: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict]:
        """Search for games with fuzzy matching"""
        # Use myrientDL's actual search
        results = await self.game_search.search(
            query=query,
            console=console,
            limit=limit
        )

        # Filter by collection if specified
        if collection:
            results = [r for r in results if r.game.collection.value == collection]

        # Convert to dicts
        return [self.db._game_to_dict(r.game) for r in results]
