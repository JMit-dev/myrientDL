"""
PostgreSQL Database Manager for FastAPI

Supports both PostgreSQL (Supabase) and SQLite for development.
"""

import os
from typing import List, Optional, Dict, Any, AsyncGenerator
from contextlib import asynccontextmanager

# Try asyncpg (PostgreSQL) first, fall back to aiosqlite
try:
    import asyncpg
    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False

import aiosqlite
from datetime import datetime

from myrientDL.models import GameFile, DownloadStatus, Collection, FileFormat


class DatabaseManager:
    """Database manager that works with both PostgreSQL and SQLite"""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.is_postgres = database_url.startswith("postgres")
        self.pool = None

    async def connect(self):
        """Initialize database connection"""
        if self.is_postgres:
            if not HAS_POSTGRES:
                raise RuntimeError("asyncpg not installed. Run: pip install asyncpg")
            self.pool = await asyncpg.create_pool(self.database_url)
            await self._create_postgres_schema()
        else:
            # SQLite - no pool needed, create schema on first use
            await self._create_sqlite_schema()

    async def disconnect(self):
        """Close database connection"""
        if self.is_postgres and self.pool:
            await self.pool.close()

    async def _create_postgres_schema(self):
        """Create PostgreSQL tables"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS game_files (
                    id SERIAL PRIMARY KEY,
                    url TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    size BIGINT,
                    parent_path TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    console TEXT,
                    region TEXT,
                    collection TEXT DEFAULT 'Unknown',
                    collection_update_frequency TEXT,
                    file_format TEXT,
                    requires_conversion BOOLEAN DEFAULT FALSE,
                    is_torrentzipped BOOLEAN DEFAULT FALSE,
                    torrentzip_crc32 TEXT,
                    checksum TEXT,
                    checksum_type TEXT,
                    last_modified TIMESTAMP,
                    etag TEXT,
                    is_recent_upload BOOLEAN DEFAULT FALSE,
                    status TEXT CHECK(status IN ('pending','downloading','completed','failed','paused')) DEFAULT 'pending',
                    local_path TEXT,
                    bytes_downloaded BIGINT DEFAULT 0,
                    download_attempts INTEGER DEFAULT 0,
                    error_message TEXT,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    average_download_speed REAL,
                    is_speed_limited BOOLEAN DEFAULT FALSE
                )
            """)

            # Create indexes
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON game_files(status)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_console ON game_files(console)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_name ON game_files(name)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_collection ON game_files(collection)")

    async def _create_sqlite_schema(self):
        """Create SQLite tables"""
        db_path = self.database_url.replace("sqlite:///", "")
        async with aiosqlite.connect(db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS game_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    size INTEGER,
                    parent_path TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    console TEXT,
                    region TEXT,
                    collection TEXT DEFAULT 'Unknown',
                    collection_update_frequency TEXT,
                    file_format TEXT,
                    requires_conversion INTEGER DEFAULT 0,
                    is_torrentzipped INTEGER DEFAULT 0,
                    torrentzip_crc32 TEXT,
                    checksum TEXT,
                    checksum_type TEXT,
                    last_modified TEXT,
                    etag TEXT,
                    is_recent_upload INTEGER DEFAULT 0,
                    status TEXT CHECK(status IN ('pending','downloading','completed','failed','paused')) DEFAULT 'pending',
                    local_path TEXT,
                    bytes_downloaded INTEGER DEFAULT 0,
                    download_attempts INTEGER DEFAULT 0,
                    error_message TEXT,
                    added_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    completed_at TEXT,
                    average_download_speed REAL,
                    is_speed_limited INTEGER DEFAULT 0
                )
            """)

            await db.execute("CREATE INDEX IF NOT EXISTS idx_status ON game_files(status)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_console ON game_files(console)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_name ON game_files(name)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_collection ON game_files(collection)")
            await db.commit()

    async def get_games(
        self,
        console: Optional[str] = None,
        collection: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """Get games with filters"""
        query = "SELECT * FROM game_files WHERE 1=1"
        params = []

        if console:
            query += f" AND console = ${len(params) + 1}" if self.is_postgres else " AND console = ?"
            params.append(console)

        if collection:
            query += f" AND collection = ${len(params) + 1}" if self.is_postgres else " AND collection = ?"
            params.append(collection)

        query += f" ORDER BY name LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}" if self.is_postgres else " ORDER BY name LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        if self.is_postgres:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query, *params)
                return [dict(row) for row in rows]
        else:
            db_path = self.database_url.replace("sqlite:///", "")
            async with aiosqlite.connect(db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(query, params) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]

    async def get_game_by_id(self, game_id: int) -> Optional[Dict]:
        """Get game by ID"""
        query = "SELECT * FROM game_files WHERE id = $1" if self.is_postgres else "SELECT * FROM game_files WHERE id = ?"

        if self.is_postgres:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(query, game_id)
                return dict(row) if row else None
        else:
            db_path = self.database_url.replace("sqlite:///", "")
            async with aiosqlite.connect(db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(query, (game_id,)) as cursor:
                    row = await cursor.fetchone()
                    return dict(row) if row else None

    async def get_collections_with_stats(self) -> List[Dict]:
        """Get all collections with game counts"""
        query = """
            SELECT
                collection,
                COUNT(*) as game_count,
                SUM(size) as total_size
            FROM game_files
            GROUP BY collection
            ORDER BY collection
        """

        if self.is_postgres:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query)
                return [dict(row) for row in rows]
        else:
            db_path = self.database_url.replace("sqlite:///", "")
            async with aiosqlite.connect(db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(query) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]

    async def get_consoles(self) -> List[str]:
        """Get list of unique consoles"""
        query = "SELECT DISTINCT console FROM game_files WHERE console IS NOT NULL ORDER BY console"

        if self.is_postgres:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query)
                return [row['console'] for row in rows]
        else:
            db_path = self.database_url.replace("sqlite:///", "")
            async with aiosqlite.connect(db_path) as db:
                async with db.execute(query) as cursor:
                    rows = await cursor.fetchall()
                    return [row[0] for row in rows]

    async def get_stats(self) -> Dict[str, Any]:
        """Get overall statistics"""
        query = """
            SELECT
                COUNT(*) as total_games,
                SUM(size) as total_size,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as downloaded_games,
                SUM(CASE WHEN status = 'completed' THEN bytes_downloaded ELSE 0 END) as downloaded_size,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending_games,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_games,
                COUNT(DISTINCT collection) as collections_count,
                COUNT(DISTINCT console) as consoles_count
            FROM game_files
        """

        if self.is_postgres:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(query)
                return dict(row)
        else:
            db_path = self.database_url.replace("sqlite:///", "")
            async with aiosqlite.connect(db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(query) as cursor:
                    row = await cursor.fetchone()
                    return dict(row)


# Dependency for FastAPI
_db_manager: Optional[DatabaseManager] = None


async def init_db():
    """Initialize database connection"""
    global _db_manager
    database_url = os.getenv("DATABASE_URL", "sqlite:///./myrient.db")
    _db_manager = DatabaseManager(database_url)
    await _db_manager.connect()


async def close_db():
    """Close database connection"""
    global _db_manager
    if _db_manager:
        await _db_manager.disconnect()


def get_db() -> DatabaseManager:
    """Get database manager instance"""
    return _db_manager
