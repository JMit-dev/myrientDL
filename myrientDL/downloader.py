import asyncio
import aiofiles
import hashlib
import time
from typing import Optional, Dict, Callable, Any
from pathlib import Path
import math

import httpx
from anyio import create_task_group, CapacityLimiter

from .models import GameFile, DownloadStatus
from .config import MyrientConfig
from .database import Database


class TokenBucket:
    """Rate limiter using token bucket algorithm"""
    
    def __init__(self, rate: float, burst: int):
        self.rate = rate  # tokens per second
        self.capacity = burst
        self.tokens = burst
        self.updated = time.monotonic()
        self._lock = asyncio.Lock()
    
    async def take(self, n: int = 1) -> None:
        """Take n tokens from the bucket, waiting if necessary"""
        async with self._lock:
            while True:
                now = time.monotonic()
                elapsed = now - self.updated
                self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
                self.updated = now
                
                if self.tokens >= n:
                    self.tokens -= n
                    return
                
                # Calculate wait time
                wait_time = (n - self.tokens) / self.rate
                await asyncio.sleep(wait_time)


class DownloadManager:
    """Manages downloads with rate limiting and resumable downloads"""
    
    def __init__(self, config: MyrientConfig, database: Database):
        self.config = config
        self.database = database
        
        # Rate limiting (per-host token buckets)
        self.rate_limiters: Dict[str, TokenBucket] = {}
        
        # Concurrency control
        self.global_semaphore = CapacityLimiter(config.concurrency.global_max)
        self.host_semaphores: Dict[str, CapacityLimiter] = {}
        
        # Progress tracking
        self.progress_callbacks: list[Callable[[GameFile, int, int], None]] = []
        self.download_stats = {
            "active_downloads": 0,
            "completed_downloads": 0,
            "failed_downloads": 0,
            "total_bytes_downloaded": 0,
            "start_time": None,
        }
        
        # HTTP client
        self.session: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        self.session = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=self.config.timeouts.connect,
                read=self.config.timeouts.read
            ),
            headers={
                "User-Agent": self.config.user_agent
            },
            follow_redirects=True
        )
        self.download_stats["start_time"] = time.time()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.aclose()
    
    def add_progress_callback(self, callback: Callable[[GameFile, int, int], None]):
        """Add a progress callback function"""
        self.progress_callbacks.append(callback)
    
    def _get_rate_limiter(self, host: str) -> TokenBucket:
        """Get or create rate limiter for host"""
        if host not in self.rate_limiters:
            self.rate_limiters[host] = TokenBucket(
                rate=self.config.rate_limit.tokens_per_sec,
                burst=self.config.rate_limit.burst
            )
        return self.rate_limiters[host]
    
    def _get_host_semaphore(self, host: str) -> CapacityLimiter:
        """Get or create semaphore for host"""
        if host not in self.host_semaphores:
            self.host_semaphores[host] = CapacityLimiter(self.config.concurrency.per_host)
        return self.host_semaphores[host]
    
    async def download_file(self, game_file: GameFile) -> bool:
        """Download a single file with resumable support"""
        from urllib.parse import urlparse
        
        host = urlparse(game_file.url).netloc
        rate_limiter = self._get_rate_limiter(host)
        host_semaphore = self._get_host_semaphore(host)
        
        async with self.global_semaphore:
            async with host_semaphore:
                return await self._download_with_retry(game_file, rate_limiter)
    
    async def _download_with_retry(self, game_file: GameFile, rate_limiter: TokenBucket) -> bool:
        """Download file with retry logic"""
        max_attempts = self.config.retries.max_attempts
        backoff_base = self.config.retries.backoff_base
        backoff_cap = self.config.retries.backoff_cap
        
        for attempt in range(max_attempts):
            try:
                # Wait for rate limiter
                await rate_limiter.take()
                
                # Update status to downloading
                game_file.status = DownloadStatus.DOWNLOADING
                game_file.download_attempts = attempt + 1
                await self.database.update_game_file(game_file)
                
                self.download_stats["active_downloads"] += 1
                
                success = await self._download_file_impl(game_file)
                
                self.download_stats["active_downloads"] -= 1
                
                if success:
                    game_file.status = DownloadStatus.COMPLETED
                    game_file.completed_at = game_file.completed_at or time.time()
                    await self.database.update_game_file(game_file)
                    self.download_stats["completed_downloads"] += 1
                    return True
                
                # If not successful, prepare for retry
                if attempt < max_attempts - 1:
                    backoff_time = min(backoff_cap, backoff_base * (2 ** attempt))
                    await asyncio.sleep(backoff_time)
                
            except Exception as e:
                game_file.error_message = str(e)
                
                if attempt < max_attempts - 1:
                    backoff_time = min(backoff_cap, backoff_base * (2 ** attempt))
                    await asyncio.sleep(backoff_time)
                else:
                    # Final failure
                    game_file.status = DownloadStatus.FAILED
                    await self.database.update_game_file(game_file)
                    self.download_stats["failed_downloads"] += 1
                    self.download_stats["active_downloads"] -= 1
                    return False
        
        # All attempts failed
        game_file.status = DownloadStatus.FAILED
        await self.database.update_game_file(game_file)
        self.download_stats["failed_downloads"] += 1
        return False
    
    async def _download_file_impl(self, game_file: GameFile) -> bool:
        """Actual file download implementation"""
        if not game_file.local_path:
            # Generate local path
            download_dir = self.config.download_root / (game_file.console or "Unknown")
            download_dir.mkdir(parents=True, exist_ok=True)
            game_file.local_path = download_dir / game_file.name
        
        temp_path = game_file.local_path.with_suffix(game_file.local_path.suffix + ".part")
        
        # Check if file already exists and is complete
        if game_file.local_path.exists():
            if game_file.size and game_file.local_path.stat().st_size == game_file.size:
                return True
        
        # Determine starting position for resumable download
        start_pos = 0
        hasher = hashlib.sha256()
        
        if temp_path.exists() and self.config.resume_downloads:
            start_pos = temp_path.stat().st_size
            
            # Re-hash existing content to continue checksum verification
            if start_pos > 0:
                async with aiofiles.open(temp_path, "rb") as f:
                    while True:
                        chunk = await f.read(8192)
                        if not chunk:
                            break
                        hasher.update(chunk)
        
        # Prepare headers for resumable download
        headers = {}
        if start_pos > 0:
            headers["Range"] = f"bytes={start_pos}-"
        
        # Download the file
        try:
            async with self.session.stream("GET", game_file.url, headers=headers) as response:
                response.raise_for_status()
                
                # Get total size from headers
                content_length = response.headers.get("content-length")
                if content_length:
                    remaining_size = int(content_length)
                    if start_pos == 0:
                        game_file.size = remaining_size
                else:
                    remaining_size = game_file.size - start_pos if game_file.size else None
                
                game_file.bytes_downloaded = start_pos
                
                # Download and write to file
                async with aiofiles.open(temp_path, "ab" if start_pos > 0 else "wb") as f:
                    downloaded_this_session = 0
                    last_progress_update = time.time()
                    
                    async for chunk in response.aiter_bytes(8192):
                        await f.write(chunk)
                        hasher.update(chunk)
                        
                        downloaded_this_session += len(chunk)
                        game_file.bytes_downloaded += len(chunk)
                        
                        # Update progress periodically
                        current_time = time.time()
                        if current_time - last_progress_update > 1.0:  # Update every second
                            for callback in self.progress_callbacks:
                                callback(game_file, game_file.bytes_downloaded, game_file.size or 0)
                            
                            # Update database
                            await self.database.update_game_file(game_file)
                            last_progress_update = current_time
                
                # Verify download completion
                if game_file.size and game_file.bytes_downloaded != game_file.size:
                    return False
                
                # Verify checksum if available
                if self.config.verify_checksums and game_file.checksum:
                    calculated_hash = hasher.hexdigest()
                    if calculated_hash.lower() != game_file.checksum.lower():
                        game_file.error_message = f"Checksum mismatch: expected {game_file.checksum}, got {calculated_hash}"
                        return False
                
                # Move temp file to final location
                temp_path.rename(game_file.local_path)
                
                # Update stats
                self.download_stats["total_bytes_downloaded"] += downloaded_this_session
                
                return True
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 416:  # Range not satisfiable
                # File might already be complete
                if temp_path.exists():
                    file_size = temp_path.stat().st_size
                    if game_file.size and file_size == game_file.size:
                        temp_path.rename(game_file.local_path)
                        return True
            raise
    
    async def download_batch(self, game_files: list[GameFile]) -> Dict[str, Any]:
        """Download multiple files concurrently"""
        results = {"successful": 0, "failed": 0, "skipped": 0}
        
        async with create_task_group() as tg:
            for game_file in game_files:
                if game_file.status == DownloadStatus.COMPLETED:
                    results["skipped"] += 1
                    continue
                
                async def download_task(gf=game_file):
                    success = await self.download_file(gf)
                    if success:
                        results["successful"] += 1
                    else:
                        results["failed"] += 1
                
                tg.start_soon(download_task)
        
        return results
    
    def get_download_speed(self) -> float:
        """Get current download speed in bytes per second"""
        if not self.download_stats["start_time"]:
            return 0.0
        
        elapsed = time.time() - self.download_stats["start_time"]
        if elapsed == 0:
            return 0.0
        
        return self.download_stats["total_bytes_downloaded"] / elapsed
    
    def get_eta(self, remaining_bytes: int) -> Optional[int]:
        """Estimate time remaining in seconds"""
        speed = self.get_download_speed()
        if speed <= 0:
            return None
        
        return int(remaining_bytes / speed)