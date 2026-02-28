import aiosqlite
import asyncio
from typing import List, Optional, Dict, Any, Union
from pathlib import Path
from datetime import datetime

from .models import GameFile, DownloadStatus, Collection, FileFormat

try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False


class Database:
    def __init__(self, db_path: Union[Path, str]):
        """
        Initialize database connection.

        Args:
            db_path: Either a Path object for SQLite or a connection string for PostgreSQL
                    PostgreSQL format: postgresql://user:pass@host:port/dbname
        """
        self.db_path = db_path
        self.is_postgres = isinstance(db_path, str) and db_path.startswith('postgresql://')
        self._pool = None  # For PostgreSQL connection pool
    
    async def __aenter__(self):
        if self.is_postgres and not self._pool:
            if not ASYNCPG_AVAILABLE:
                raise ImportError("asyncpg is required for PostgreSQL support. Install with: pip install asyncpg")
            self._pool = await asyncpg.create_pool(self.db_path)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._pool:
            await self._pool.close()
    
    async def init_db(self):
        """Initialize the database with required tables"""
        if self.is_postgres:
            await self._init_postgres()
        else:
            await self._init_sqlite()

    async def _init_sqlite(self):
        """Initialize SQLite database"""
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
            await db.execute("CREATE INDEX IF NOT EXISTS idx_collection ON game_files(collection)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_file_format ON game_files(file_format)")

            await db.commit()

    async def _init_postgres(self):
        """Initialize PostgreSQL database"""
        if not self._pool:
            self._pool = await asyncpg.create_pool(self.db_path)

        async with self._pool.acquire() as conn:
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

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS download_sessions (
                    id SERIAL PRIMARY KEY,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ended_at TIMESTAMP,
                    total_files INTEGER DEFAULT 0,
                    completed_files INTEGER DEFAULT 0,
                    failed_files INTEGER DEFAULT 0,
                    total_bytes BIGINT DEFAULT 0,
                    downloaded_bytes BIGINT DEFAULT 0
                )
            """)

            # Create indexes for better performance
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON game_files(status)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_console ON game_files(console)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_name ON game_files(name)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_parent_path ON game_files(parent_path)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_collection ON game_files(collection)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_file_format ON game_files(file_format)")
    
    async def add_game_file(self, game_file: GameFile) -> bool:
        """Add a game file to the database. Returns True if added, False if already exists"""
        if self.is_postgres:
            return await self._add_game_file_postgres(game_file)
        else:
            return await self._add_game_file_sqlite(game_file)

    async def _add_game_file_sqlite(self, game_file: GameFile) -> bool:
        """SQLite implementation"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute("""
                    INSERT INTO game_files (
                        url, name, size, parent_path, file_type, console, region,
                        collection, collection_update_frequency, file_format,
                        requires_conversion, is_torrentzipped, torrentzip_crc32,
                        checksum, checksum_type, last_modified, etag, is_recent_upload,
                        status, local_path, bytes_downloaded, download_attempts, error_message,
                        added_at, completed_at, average_download_speed, is_speed_limited
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    game_file.url, game_file.name, game_file.size, game_file.parent_path,
                    game_file.file_type, game_file.console, game_file.region,
                    game_file.collection.value, game_file.collection_update_frequency,
                    game_file.file_format.value if game_file.file_format else None,
                    int(game_file.requires_conversion), int(game_file.is_torrentzipped),
                    game_file.torrentzip_crc32,
                    game_file.checksum, game_file.checksum_type,
                    game_file.last_modified.isoformat() if game_file.last_modified else None,
                    game_file.etag, int(game_file.is_recent_upload),
                    game_file.status.value,
                    str(game_file.local_path) if game_file.local_path else None,
                    game_file.bytes_downloaded, game_file.download_attempts, game_file.error_message,
                    game_file.added_at.isoformat(),
                    game_file.completed_at.isoformat() if game_file.completed_at else None,
                    game_file.average_download_speed, int(game_file.is_speed_limited)
                ))
                await db.commit()
                return True
            except aiosqlite.IntegrityError:
                return False

    async def _add_game_file_postgres(self, game_file: GameFile) -> bool:
        """PostgreSQL implementation"""
        async with self._pool.acquire() as conn:
            try:
                await conn.execute("""
                    INSERT INTO game_files (
                        url, name, size, parent_path, file_type, console, region,
                        collection, collection_update_frequency, file_format,
                        requires_conversion, is_torrentzipped, torrentzip_crc32,
                        checksum, checksum_type, last_modified, etag, is_recent_upload,
                        status, local_path, bytes_downloaded, download_attempts, error_message,
                        added_at, completed_at, average_download_speed, is_speed_limited
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25, $26, $27)
                """,
                    game_file.url, game_file.name, game_file.size, game_file.parent_path,
                    game_file.file_type, game_file.console, game_file.region,
                    game_file.collection.value, game_file.collection_update_frequency,
                    game_file.file_format.value if game_file.file_format else None,
                    game_file.requires_conversion, game_file.is_torrentzipped,
                    game_file.torrentzip_crc32,
                    game_file.checksum, game_file.checksum_type,
                    game_file.last_modified,
                    game_file.etag, game_file.is_recent_upload,
                    game_file.status.value,
                    str(game_file.local_path) if game_file.local_path else None,
                    game_file.bytes_downloaded, game_file.download_attempts, game_file.error_message,
                    game_file.added_at,
                    game_file.completed_at,
                    game_file.average_download_speed, game_file.is_speed_limited
                )
                return True
            except asyncpg.UniqueViolationError:
                return False
    
    async def update_game_file(self, game_file: GameFile):
        """Update an existing game file in the database"""
        if self.is_postgres:
            await self._update_game_file_postgres(game_file)
        else:
            await self._update_game_file_sqlite(game_file)

    async def _update_game_file_sqlite(self, game_file: GameFile):
        """SQLite implementation"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE game_files SET
                    name=?, size=?, parent_path=?, file_type=?, console=?, region=?,
                    collection=?, collection_update_frequency=?, file_format=?,
                    requires_conversion=?, is_torrentzipped=?, torrentzip_crc32=?,
                    checksum=?, checksum_type=?, last_modified=?, etag=?, is_recent_upload=?,
                    status=?, local_path=?, bytes_downloaded=?, download_attempts=?, error_message=?,
                    completed_at=?, average_download_speed=?, is_speed_limited=?
                WHERE url=?
            """, (
                game_file.name, game_file.size, game_file.parent_path, game_file.file_type,
                game_file.console, game_file.region,
                game_file.collection.value, game_file.collection_update_frequency,
                game_file.file_format.value if game_file.file_format else None,
                int(game_file.requires_conversion), int(game_file.is_torrentzipped),
                game_file.torrentzip_crc32,
                game_file.checksum, game_file.checksum_type,
                game_file.last_modified.isoformat() if game_file.last_modified else None,
                game_file.etag, int(game_file.is_recent_upload),
                game_file.status.value,
                str(game_file.local_path) if game_file.local_path else None,
                game_file.bytes_downloaded, game_file.download_attempts, game_file.error_message,
                game_file.completed_at.isoformat() if game_file.completed_at else None,
                game_file.average_download_speed, int(game_file.is_speed_limited),
                game_file.url
            ))
            await db.commit()

    async def _update_game_file_postgres(self, game_file: GameFile):
        """PostgreSQL implementation"""
        async with self._pool.acquire() as conn:
            await conn.execute("""
                UPDATE game_files SET
                    name=$1, size=$2, parent_path=$3, file_type=$4, console=$5, region=$6,
                    collection=$7, collection_update_frequency=$8, file_format=$9,
                    requires_conversion=$10, is_torrentzipped=$11, torrentzip_crc32=$12,
                    checksum=$13, checksum_type=$14, last_modified=$15, etag=$16, is_recent_upload=$17,
                    status=$18, local_path=$19, bytes_downloaded=$20, download_attempts=$21, error_message=$22,
                    completed_at=$23, average_download_speed=$24, is_speed_limited=$25
                WHERE url=$26
            """,
                game_file.name, game_file.size, game_file.parent_path, game_file.file_type,
                game_file.console, game_file.region,
                game_file.collection.value, game_file.collection_update_frequency,
                game_file.file_format.value if game_file.file_format else None,
                game_file.requires_conversion, game_file.is_torrentzipped,
                game_file.torrentzip_crc32,
                game_file.checksum, game_file.checksum_type,
                game_file.last_modified,
                game_file.etag, game_file.is_recent_upload,
                game_file.status.value,
                str(game_file.local_path) if game_file.local_path else None,
                game_file.bytes_downloaded, game_file.download_attempts, game_file.error_message,
                game_file.completed_at,
                game_file.average_download_speed, game_file.is_speed_limited,
                game_file.url
            )
    
    async def get_game_file(self, url: str) -> Optional[GameFile]:
        """Get a game file by URL"""
        if self.is_postgres:
            return await self._get_game_file_postgres(url)
        else:
            return await self._get_game_file_sqlite(url)

    async def _get_game_file_sqlite(self, url: str) -> Optional[GameFile]:
        """SQLite implementation"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT * FROM game_files WHERE url=?", (url,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return self._row_to_game_file(row)
                return None

    async def _get_game_file_postgres(self, url: str) -> Optional[GameFile]:
        """PostgreSQL implementation"""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM game_files WHERE url=$1", url)
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
        if self.is_postgres:
            return await self._get_game_files_postgres(status, console, limit, offset)
        else:
            return await self._get_game_files_sqlite(status, console, limit, offset)

    async def _get_game_files_sqlite(
        self,
        status: Optional[DownloadStatus] = None,
        console: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[GameFile]:
        """SQLite implementation"""
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

    async def _get_game_files_postgres(
        self,
        status: Optional[DownloadStatus] = None,
        console: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[GameFile]:
        """PostgreSQL implementation"""
        query = "SELECT * FROM game_files WHERE 1=1"
        params = []
        param_num = 1

        if status:
            query += f" AND status=${param_num}"
            params.append(status.value)
            param_num += 1

        if console:
            query += f" AND console=${param_num}"
            params.append(console)
            param_num += 1

        query += " ORDER BY added_at DESC"

        if limit:
            query += f" LIMIT ${param_num} OFFSET ${param_num + 1}"
            params.extend([limit, offset])

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [self._row_to_game_file(row) for row in rows]
    
    async def search_games(self, search_term: str, limit: int = 50) -> List[GameFile]:
        """Search for games by name (case-insensitive)"""
        if self.is_postgres:
            return await self._search_games_postgres(search_term, limit)
        else:
            return await self._search_games_sqlite(search_term, limit)

    async def _search_games_sqlite(self, search_term: str, limit: int = 50) -> List[GameFile]:
        """SQLite implementation"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT * FROM game_files WHERE name LIKE ? ORDER BY name LIMIT ?",
                (f"%{search_term}%", limit)
            ) as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_game_file(row) for row in rows]

    async def _search_games_postgres(self, search_term: str, limit: int = 50) -> List[GameFile]:
        """PostgreSQL implementation"""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM game_files WHERE name ILIKE $1 ORDER BY name LIMIT $2",
                f"%{search_term}%", limit
            )
            return [self._row_to_game_file(row) for row in rows]
    
    async def get_consoles(self) -> List[str]:
        """Get list of unique consoles"""
        if self.is_postgres:
            return await self._get_consoles_postgres()
        else:
            return await self._get_consoles_sqlite()

    async def _get_consoles_sqlite(self) -> List[str]:
        """SQLite implementation"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT DISTINCT console FROM game_files WHERE console IS NOT NULL ORDER BY console"
            ) as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]

    async def _get_consoles_postgres(self) -> List[str]:
        """PostgreSQL implementation"""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT DISTINCT console FROM game_files WHERE console IS NOT NULL ORDER BY console"
            )
            return [row['console'] for row in rows]

    async def get_collections(self) -> List[str]:
        """Get list of unique collections"""
        if self.is_postgres:
            return await self._get_collections_postgres()
        else:
            return await self._get_collections_sqlite()

    async def _get_collections_sqlite(self) -> List[str]:
        """SQLite implementation"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT DISTINCT collection FROM game_files WHERE collection IS NOT NULL ORDER BY collection"
            ) as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]

    async def _get_collections_postgres(self) -> List[str]:
        """PostgreSQL implementation"""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT DISTINCT collection FROM game_files WHERE collection IS NOT NULL ORDER BY collection"
            )
            return [row['collection'] for row in rows]

    async def get_games_by_collection(self, collection: str, limit: Optional[int] = None) -> List[GameFile]:
        """Get all games from a specific collection"""
        if self.is_postgres:
            return await self._get_games_by_collection_postgres(collection, limit)
        else:
            return await self._get_games_by_collection_sqlite(collection, limit)

    async def _get_games_by_collection_sqlite(self, collection: str, limit: Optional[int] = None) -> List[GameFile]:
        """SQLite implementation"""
        query = "SELECT * FROM game_files WHERE collection=? ORDER BY name"
        params = [collection]

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_game_file(row) for row in rows]

    async def _get_games_by_collection_postgres(self, collection: str, limit: Optional[int] = None) -> List[GameFile]:
        """PostgreSQL implementation"""
        query = "SELECT * FROM game_files WHERE collection=$1 ORDER BY name"
        params = [collection]

        if limit:
            query += " LIMIT $2"
            params.append(limit)

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [self._row_to_game_file(row) for row in rows]
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get download statistics"""
        if self.is_postgres:
            return await self._get_stats_postgres()
        else:
            return await self._get_stats_sqlite()

    async def _get_stats_sqlite(self) -> Dict[str, Any]:
        """SQLite implementation"""
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

    async def _get_stats_postgres(self) -> Dict[str, Any]:
        """PostgreSQL implementation"""
        async with self._pool.acquire() as conn:
            stats = {}

            # Count by status
            status_counts = await conn.fetch(
                "SELECT status, COUNT(*) FROM game_files GROUP BY status"
            )
            stats["status_counts"] = {row['status']: row['count'] for row in status_counts}

            # Total sizes
            row = await conn.fetchrow(
                "SELECT SUM(size) as total_size, SUM(bytes_downloaded) as downloaded_bytes FROM game_files WHERE size IS NOT NULL"
            )
            stats["total_size"] = row['total_size'] or 0 if row else 0
            stats["downloaded_bytes"] = row['downloaded_bytes'] or 0 if row else 0

            # Console breakdown
            console_counts = await conn.fetch(
                "SELECT console, COUNT(*) FROM game_files WHERE console IS NOT NULL GROUP BY console ORDER BY COUNT(*) DESC"
            )
            stats["console_counts"] = {row['console']: row['count'] for row in console_counts}

            return stats
    
    def _row_to_game_file(self, row) -> GameFile:
        """Convert database row to GameFile object

        Handles both SQLite tuple rows (accessed by index) and PostgreSQL Record objects (accessed by column name or index)
        """
        # Check if this is a PostgreSQL Record object (has keys() method) or SQLite tuple
        is_postgres_record = hasattr(row, 'keys')

        if is_postgres_record:
            # PostgreSQL Record - access by column name
            return GameFile(
                url=row['url'],
                name=row['name'],
                size=row['size'],
                parent_path=row['parent_path'],
                file_type=row['file_type'],
                console=row['console'],
                region=row['region'],
                collection=Collection(row['collection']) if row['collection'] else Collection.UNKNOWN,
                collection_update_frequency=row['collection_update_frequency'],
                file_format=FileFormat(row['file_format']) if row['file_format'] else None,
                requires_conversion=bool(row['requires_conversion']),
                is_torrentzipped=bool(row['is_torrentzipped']),
                torrentzip_crc32=row['torrentzip_crc32'],
                checksum=row['checksum'],
                checksum_type=row['checksum_type'],
                last_modified=row['last_modified'],
                etag=row['etag'],
                is_recent_upload=bool(row['is_recent_upload']),
                status=DownloadStatus(row['status']),
                local_path=Path(row['local_path']) if row['local_path'] else None,
                bytes_downloaded=row['bytes_downloaded'],
                download_attempts=row['download_attempts'],
                error_message=row['error_message'],
                added_at=row['added_at'],
                completed_at=row['completed_at'],
                average_download_speed=row['average_download_speed'],
                is_speed_limited=bool(row['is_speed_limited'])
            )
        else:
            # SQLite tuple - access by index
            return GameFile(
                url=row[1],
                name=row[2],
                size=row[3],
                parent_path=row[4],
                file_type=row[5],
                console=row[6],
                region=row[7],
                collection=Collection(row[8]) if row[8] else Collection.UNKNOWN,
                collection_update_frequency=row[9],
                file_format=FileFormat(row[10]) if row[10] else None,
                requires_conversion=bool(row[11]),
                is_torrentzipped=bool(row[12]),
                torrentzip_crc32=row[13],
                checksum=row[14],
                checksum_type=row[15],
                last_modified=datetime.fromisoformat(row[16]) if row[16] else None,
                etag=row[17],
                is_recent_upload=bool(row[18]),
                status=DownloadStatus(row[19]),
                local_path=Path(row[20]) if row[20] else None,
                bytes_downloaded=row[21],
                download_attempts=row[22],
                error_message=row[23],
                added_at=datetime.fromisoformat(row[24]),
                completed_at=datetime.fromisoformat(row[25]) if row[25] else None,
                average_download_speed=row[26],
                is_speed_limited=bool(row[27])
            )