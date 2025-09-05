from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum
from pathlib import Path


class DownloadStatus(str, Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


class GameFile(BaseModel):
    """Represents a game file discovered during crawling"""
    url: str
    name: str
    size: Optional[int] = None
    parent_path: str  # e.g., "No-Intro/Nintendo - Game Boy"
    file_type: str  # e.g., "zip", "7z"
    console: Optional[str] = None  # extracted from parent path
    region: Optional[str] = None  # extracted from filename
    
    # Metadata
    checksum: Optional[str] = None
    checksum_type: Optional[str] = None
    last_modified: Optional[datetime] = None
    etag: Optional[str] = None
    
    # Download tracking
    status: DownloadStatus = DownloadStatus.PENDING
    local_path: Optional[Path] = None
    bytes_downloaded: int = 0
    download_attempts: int = 0
    error_message: Optional[str] = None
    added_at: datetime = datetime.now()
    completed_at: Optional[datetime] = None
    
    def __str__(self) -> str:
        return f"{self.console or 'Unknown'}: {self.name}"
    
    @property
    def download_progress(self) -> float:
        """Return download progress as percentage (0.0 to 1.0)"""
        if not self.size or self.size == 0:
            return 0.0
        return min(self.bytes_downloaded / self.size, 1.0)
    
    @property
    def size_mb(self) -> float:
        """Return file size in MB"""
        if not self.size:
            return 0.0
        return self.size / (1024 * 1024)


class CrawlResult(BaseModel):
    """Result of crawling a directory"""
    url: str
    files: list[GameFile]
    subdirectories: list[str]
    total_size: int = 0
    crawled_at: datetime = datetime.now()


class DownloadStats(BaseModel):
    """Overall download statistics"""
    total_files: int = 0
    pending_files: int = 0
    downloading_files: int = 0
    completed_files: int = 0
    failed_files: int = 0
    
    total_size_bytes: int = 0
    downloaded_bytes: int = 0
    download_speed_bps: float = 0.0  # bytes per second
    
    eta_seconds: Optional[int] = None
    active_downloads: list[str] = []  # URLs currently being downloaded
    
    @property
    def progress_percentage(self) -> float:
        """Overall progress as percentage"""
        if self.total_size_bytes == 0:
            return 0.0
        return (self.downloaded_bytes / self.total_size_bytes) * 100.0
    
    @property
    def download_speed_mbps(self) -> float:
        """Download speed in MB/s"""
        return self.download_speed_bps / (1024 * 1024)