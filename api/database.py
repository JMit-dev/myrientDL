"""
Database Manager for FastAPI

Wraps myrientDL's database functionality for the API.
"""

import os
from typing import List, Optional, Dict, Any
from pathlib import Path
from myrientDL.database import Database
from myrientDL.config import MyrientConfig
from myrientDL.models import GameFile


class DatabaseManager:
    """Wrapper around myrientDL's Database for API use"""

    def __init__(self, db_path: str = "./myrient.db"):
        self.db_path = Path(db_path)
        self.db = Database(self.db_path)

    async def connect(self):
        """Initialize database connection (creates tables if needed)"""
        # myrient's DB doesn't need async init, tables created on first use
        pass

    async def disconnect(self):
        """Close database connection"""
        pass

    async def get_games(
        self,
        console: Optional[str] = None,
        collection: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """Get games with filters"""
        # Use correct method name: get_game_files not get_all_games
        games = await self.db.get_game_files()

        # Filter by console
        if console:
            games = [g for g in games if g.console == console]

        # Filter by collection
        if collection:
            games = [g for g in games if g.collection.value == collection]

        # Apply pagination
        games = games[offset:offset + limit]

        # Convert to dicts with extra fields
        return [self._game_to_dict(g) for g in games]

    async def get_game_by_id(self, game_id: int) -> Optional[Dict]:
        """Get game by ID"""
        # Use correct method name: get_game_file not get_game
        game = await self.db.get_game_file(game_id)
        return self._game_to_dict(game) if game else None

    async def get_collections_with_stats(self) -> List[Dict]:
        """Get all collections with game counts"""
        collections = await self.db.get_collections()
        result = []

        for collection in collections:
            games = await self.db.get_games_by_collection(collection)
            total_size = sum(g.size or 0 for g in games)

            result.append({
                "name": collection.value,
                "game_count": len(games),
                "total_size": total_size,
                "update_frequency": "Varies",
                "content_type": "Games"
            })

        return result

    async def get_consoles(self) -> List[str]:
        """Get list of unique consoles"""
        consoles = await self.db.get_consoles()
        return consoles

    async def get_stats(self) -> Dict[str, Any]:
        """Get overall statistics"""
        stats = await self.db.get_stats()
        return stats

    def _game_to_dict(self, game: GameFile) -> Dict:
        """Convert GameFile to dict for API response"""
        return {
            "id": game.id,
            "url": game.url,
            "name": game.name,
            "size": game.size,
            "console": game.console,
            "region": game.region,
            "collection": game.collection.value,
            "file_format": game.file_format.value if game.file_format else None,
            "requires_conversion": game.requires_conversion,
            "status": game.status.value,
            "bytes_downloaded": game.bytes_downloaded,
            "download_progress": game.download_progress,
            "formatted_size": game.formatted_size,
        }


# Dependency for FastAPI
_db_manager: Optional[DatabaseManager] = None


async def init_db():
    """Initialize database connection"""
    global _db_manager
    # Use DATABASE_URL env var if set, otherwise default to SQLite
    db_url = os.getenv("DATABASE_URL", "sqlite:///./myrient.db")

    # Extract path from URL (handle both sqlite:/// and postgres:// formats)
    if db_url.startswith("sqlite:///"):
        db_path = db_url.replace("sqlite:///", "")
    else:
        # For PostgreSQL, we'll need to use SQLite locally for now
        # TODO: Implement PostgreSQL support in myrientDL.database
        db_path = "./myrient.db"

    _db_manager = DatabaseManager(db_path)
    await _db_manager.connect()


async def close_db():
    """Close database connection"""
    global _db_manager
    if _db_manager:
        await _db_manager.disconnect()


def get_db() -> DatabaseManager:
    """Get database manager instance"""
    return _db_manager
