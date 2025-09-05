import aiosqlite
import asyncio
from typing import List, Optional, Dict, Any
from pathlib import Path
from datetime import datetime

from .models import GameFile, DownloadStatus


class Database:
    def __init__(self, db_path: Path):
        self.db_path = db_path
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
    
    async def init_db(self):
        """Initialize the database with required tables"""
        async with aiosqlite.connect(self.db_path) as db:
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
                    checksum TEXT,
                    checksum_type TEXT,
                    last_modified TEXT,
                    etag TEXT,
                    status TEXT CHECK(status IN ('pending','downloading','completed','failed','paused')) DEFAULT 'pending',
                    local_path TEXT,
                    bytes_downloaded INTEGER DEFAULT 0,
                    download_attempts INTEGER DEFAULT 0,
                    error_message TEXT,
                    added_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    completed_at TEXT
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS download_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    ended_at TEXT,
                    total_files INTEGER DEFAULT 0,
                    completed_files INTEGER DEFAULT 0,
                    failed_files INTEGER DEFAULT 0,
                    total_bytes INTEGER DEFAULT 0,
                    downloaded_bytes INTEGER DEFAULT 0
                )
            """)
            
            # Create indexes for better performance
            await db.execute("CREATE INDEX IF NOT EXISTS idx_status ON game_files(status)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_console ON game_files(console)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_name ON game_files(name)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_parent_path ON game_files(parent_path)")
            
            await db.commit()
    
    async def add_game_file(self, game_file: GameFile) -> bool:
        """Add a game file to the database. Returns True if added, False if already exists"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute("""
                    INSERT INTO game_files (
                        url, name, size, parent_path, file_type, console, region,
                        checksum, checksum_type, last_modified, etag, status,
                        local_path, bytes_downloaded, download_attempts, error_message,
                        added_at, completed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    game_file.url, game_file.name, game_file.size, game_file.parent_path,
                    game_file.file_type, game_file.console, game_file.region,
                    game_file.checksum, game_file.checksum_type, 
                    game_file.last_modified.isoformat() if game_file.last_modified else None,
                    game_file.etag, game_file.status.value,
                    str(game_file.local_path) if game_file.local_path else None,
                    game_file.bytes_downloaded, game_file.download_attempts, game_file.error_message,
                    game_file.added_at.isoformat(), 
                    game_file.completed_at.isoformat() if game_file.completed_at else None
                ))
                await db.commit()
                return True
            except aiosqlite.IntegrityError:
                return False
    
    async def update_game_file(self, game_file: GameFile):
        """Update an existing game file in the database"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE game_files SET
                    name=?, size=?, parent_path=?, file_type=?, console=?, region=?,
                    checksum=?, checksum_type=?, last_modified=?, etag=?, status=?,
                    local_path=?, bytes_downloaded=?, download_attempts=?, error_message=?,
                    completed_at=?
                WHERE url=?
            """, (
                game_file.name, game_file.size, game_file.parent_path, game_file.file_type,
                game_file.console, game_file.region, game_file.checksum, game_file.checksum_type,
                game_file.last_modified.isoformat() if game_file.last_modified else None,
                game_file.etag, game_file.status.value,
                str(game_file.local_path) if game_file.local_path else None,
                game_file.bytes_downloaded, game_file.download_attempts, game_file.error_message,
                game_file.completed_at.isoformat() if game_file.completed_at else None,
                game_file.url
            ))
            await db.commit()
    
    async def get_game_file(self, url: str) -> Optional[GameFile]:
        """Get a game file by URL"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT * FROM game_files WHERE url=?", (url,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return self._row_to_game_file(row)
                return None
    
    async def get_game_files(
        self, 
        status: Optional[DownloadStatus] = None,
        console: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[GameFile]:
        """Get game files with optional filtering"""
        query = "SELECT * FROM game_files WHERE 1=1"
        params = []
        
        if status:
            query += " AND status=?"
            params.append(status.value)
        
        if console:
            query += " AND console=?"
            params.append(console)
        
        query += " ORDER BY added_at DESC"
        
        if limit:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_game_file(row) for row in rows]
    
    async def search_games(self, search_term: str, limit: int = 50) -> List[GameFile]:
        """Search for games by name (case-insensitive)"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT * FROM game_files WHERE name LIKE ? ORDER BY name LIMIT ?",
                (f"%{search_term}%", limit)
            ) as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_game_file(row) for row in rows]
    
    async def get_consoles(self) -> List[str]:
        """Get list of unique consoles"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT DISTINCT console FROM game_files WHERE console IS NOT NULL ORDER BY console"
            ) as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get download statistics"""
        async with aiosqlite.connect(self.db_path) as db:
            stats = {}
            
            # Count by status
            async with db.execute(
                "SELECT status, COUNT(*) FROM game_files GROUP BY status"
            ) as cursor:
                status_counts = await cursor.fetchall()
                stats["status_counts"] = dict(status_counts)
            
            # Total sizes
            async with db.execute(
                "SELECT SUM(size), SUM(bytes_downloaded) FROM game_files WHERE size IS NOT NULL"
            ) as cursor:
                row = await cursor.fetchone()
                stats["total_size"] = row[0] or 0
                stats["downloaded_bytes"] = row[1] or 0
            
            # Console breakdown
            async with db.execute(
                "SELECT console, COUNT(*) FROM game_files WHERE console IS NOT NULL GROUP BY console ORDER BY COUNT(*) DESC"
            ) as cursor:
                console_counts = await cursor.fetchall()
                stats["console_counts"] = dict(console_counts)
            
            return stats
    
    def _row_to_game_file(self, row) -> GameFile:
        """Convert database row to GameFile object"""
        return GameFile(
            url=row[1],
            name=row[2],
            size=row[3],
            parent_path=row[4],
            file_type=row[5],
            console=row[6],
            region=row[7],
            checksum=row[8],
            checksum_type=row[9],
            last_modified=datetime.fromisoformat(row[10]) if row[10] else None,
            etag=row[11],
            status=DownloadStatus(row[12]),
            local_path=Path(row[13]) if row[13] else None,
            bytes_downloaded=row[14],
            download_attempts=row[15],
            error_message=row[16],
            added_at=datetime.fromisoformat(row[17]),
            completed_at=datetime.fromisoformat(row[18]) if row[18] else None,
        )