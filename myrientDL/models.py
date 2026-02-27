from pydantic import BaseModel, Field
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


class Collection(str, Enum):
    """Myrient archive collections with their purposes and update schedules"""
    NO_INTRO = "No-Intro"  # Non-optical disk systems (Weekly)
    REDUMP = "Redump"  # Optical disc systems (Weekly)
    MAME = "MAME"  # MAME arcade (Weekly)
    HBMAME = "HBMAME"  # Homebrew arcade (Weekly)
    TOSEC = "TOSEC"  # Non-optical disk software (Weekly)
    TOSEC_ISO = "TOSEC-ISO"  # Optical disc software (Weekly)
    TOSEC_PIX = "TOSEC-PIX"  # Scans of manuals/magazines (Weekly)
    FBNEO = "FinalBurn Neo"  # FinalBurn Neo arcade (Weekly)
    TEKNOPARROT = "TeknoParrot"  # TeknoParrot arcade (Weekly)
    TOTAL_DOS = "Total DOS Collection"  # DOS games (Weekly)
    LASERDISC = "Laserdisc Collection"  # Laserdisc content (Weekly)
    LOST_LEVELS = "Lost Levels"  # Uncataloged content (Weekly)
    HTGD = "Hardware Target Game Database"  # Flash cart content (Weekly)
    RETRO_ACHIEVEMENTS = "RetroAchievements"  # RetroAchievements compatible (Weekly)
    T_EN = "T-En Collection"  # English translations (Weekly)
    TOUHOU = "Touhou Project Collection"  # Touhou series (Weekly)
    EGGMAN = "Eggman's Arcade Repository"  # Arcade dumps (Weekly)
    INTERNET_ARCHIVE = "Internet Archive"  # At-risk content (On request)
    MISCELLANEOUS = "Miscellaneous"  # Requested content (On request)
    BITSAVERS = "Bitsavers"  # Vintage computer software (Daily)
    EXO = "eXo"  # Platform preservation (On request)
    UNKNOWN = "Unknown"


class FileFormat(str, Enum):
    """Game file formats with special handling requirements"""
    ZIP = "zip"  # Standard ZIP archives
    SEVEN_Z = "7z"  # 7-Zip archives
    RAR = "rar"  # RAR archives
    ISO = "iso"  # ISO disc images
    BIN_CUE = "bin"  # BIN/CUE disc images
    RVZ = "rvz"  # Dolphin compressed GameCube/Wii (needs conversion)
    WUX = "wux"  # Compressed Wii U (needs conversion)
    CHD = "chd"  # Compressed Hunks of Data (MAME)
    GCZ = "gcz"  # Dolphin GCZ compressed
    NKI = "nki"  # Kontakt instrument
    WBF = "wbfs"  # Wii Backup File System
    OTHER = "other"


class GameFile(BaseModel):
    """Represents a game file discovered during crawling"""
    url: str
    name: str
    size: Optional[int] = None
    parent_path: str  # e.g., "No-Intro/Nintendo - Game Boy"
    file_type: str  # e.g., "zip", "7z"
    console: Optional[str] = None  # extracted from parent path
    region: Optional[str] = None  # extracted from filename

    # Collection metadata
    collection: Collection = Collection.UNKNOWN
    collection_update_frequency: Optional[str] = None  # "Weekly", "Daily", "On request"

    # Enhanced file format metadata
    file_format: Optional[FileFormat] = None
    requires_conversion: bool = False  # True for RVZ, WUX
    is_torrentzipped: bool = False  # True if ZIP has TORRENTZIPPED comment
    torrentzip_crc32: Optional[str] = None  # CRC-32 from TORRENTZIPPED-XXXXXXXX

    # Metadata
    checksum: Optional[str] = None
    checksum_type: Optional[str] = None
    last_modified: Optional[datetime] = None
    etag: Optional[str] = None

    # Recent update warning
    is_recent_upload: bool = False  # True if < 24 hours old (may not be propagated)

    # Download tracking
    status: DownloadStatus = DownloadStatus.PENDING
    local_path: Optional[Path] = None
    bytes_downloaded: int = 0
    download_attempts: int = 0
    error_message: Optional[str] = None
    added_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    # Download speed tracking for abuse detection
    average_download_speed: Optional[float] = None  # bytes per second
    is_speed_limited: bool = False  # True if detected 10 KB/s limit
    
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

    @property
    def size_gb(self) -> float:
        """Return file size in GB"""
        if not self.size:
            return 0.0
        return self.size / (1024 * 1024 * 1024)

    @property
    def formatted_size(self) -> str:
        """Return human-readable file size"""
        if not self.size:
            return "Unknown"

        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if self.size < 1024.0:
                return f"{self.size:.2f} {unit}"
            self.size /= 1024.0
        return f"{self.size:.2f} PB"

    @property
    def needs_special_handling(self) -> bool:
        """Returns True if file needs special handling (conversion, etc.)"""
        return self.requires_conversion or self.file_format in [FileFormat.RVZ, FileFormat.WUX]

    @property
    def collection_info(self) -> str:
        """Returns collection name with update frequency"""
        if self.collection_update_frequency:
            return f"{self.collection.value} ({self.collection_update_frequency})"
        return self.collection.value

    def get_conversion_info(self) -> Optional[str]:
        """Returns conversion instructions for special formats"""
        if self.file_format == FileFormat.RVZ:
            return "RVZ format requires Dolphin emulator for conversion to ISO. See Myrient FAQ for instructions."
        elif self.file_format == FileFormat.WUX:
            return "WUX format requires WudCompress tool for conversion to ISO/WUD. See Myrient FAQ for instructions."
        return None


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

    # Speed monitoring for abuse detection
    speed_limited_downloads: int = 0  # Count of downloads limited to ~10 KB/s
    average_speed_bps: float = 0.0  # Average across all downloads

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

    @property
    def download_speed_kbps(self) -> float:
        """Download speed in KB/s"""
        return self.download_speed_bps / 1024

    @property
    def is_potentially_throttled(self) -> bool:
        """Check if downloads appear to be throttled (around 10 KB/s)"""
        # Myrient throttles abusive downloads to 10 KB/s
        return 8_000 <= self.download_speed_bps <= 12_000


class CollectionInfo(BaseModel):
    """Information about a Myrient collection"""
    name: Collection
    description: str
    update_frequency: str  # "Weekly", "Daily", "On request"
    content_type: str  # "Optical disc", "Cartridge", "Arcade", etc.
    primary_use: str  # Description of what the collection is for

    @staticmethod
    def get_collection_details(collection: Collection) -> "CollectionInfo":
        """Get detailed information about a collection"""
        collection_map = {
            Collection.NO_INTRO: CollectionInfo(
                name=Collection.NO_INTRO,
                description="Content for non-optical disk-based systems and digital platforms",
                update_frequency="Weekly",
                content_type="Cartridge/Digital",
                primary_use="Cartridge-based consoles (NES, SNES, Game Boy, etc.)"
            ),
            Collection.REDUMP: CollectionInfo(
                name=Collection.REDUMP,
                description="Content for optical disc-based systems",
                update_frequency="Weekly",
                content_type="Optical Disc",
                primary_use="Disc-based consoles (PlayStation, Xbox, GameCube, etc.)"
            ),
            Collection.MAME: CollectionInfo(
                name=Collection.MAME,
                description="Content for the MAME arcade emulator",
                update_frequency="Weekly",
                content_type="Arcade",
                primary_use="Arcade games compatible with MAME"
            ),
            Collection.TOSEC: CollectionInfo(
                name=Collection.TOSEC,
                description="Software for various non-optical disk-based electronics",
                update_frequency="Weekly",
                content_type="Software",
                primary_use="Computer software and utilities"
            ),
            Collection.BITSAVERS: CollectionInfo(
                name=Collection.BITSAVERS,
                description="Software and documentation for vintage computers",
                update_frequency="Daily",
                content_type="Vintage Software",
                primary_use="Historical computer preservation"
            ),
        }
        return collection_map.get(collection, CollectionInfo(
            name=collection,
            description="Unknown collection",
            update_frequency="Unknown",
            content_type="Unknown",
            primary_use="Unknown"
        ))


class DownloadWarning(BaseModel):
    """Warnings about downloads or files"""
    severity: str  # "info", "warning", "error"
    message: str
    suggestion: Optional[str] = None
    game_url: Optional[str] = None

    @staticmethod
    def speed_limit_warning(game_url: str) -> "DownloadWarning":
        """Warning for speed-limited downloads"""
        return DownloadWarning(
            severity="warning",
            message="Download speed limited to ~10 KB/s - possible abuse detection",
            suggestion=(
                "Ensure you're downloading directly from Myrient and not through a third-party site. "
                "Disable browser extensions and ensure your download manager is up to date."
            ),
            game_url=game_url
        )

    @staticmethod
    def recent_upload_warning(game_url: str) -> "DownloadWarning":
        """Warning for recently uploaded files"""
        return DownloadWarning(
            severity="info",
            message="File uploaded within last 24 hours - may not be available on all servers",
            suggestion="If download fails, try again later (files take up to 24 hours to propagate)",
            game_url=game_url
        )

    @staticmethod
    def conversion_required_warning(game_url: str, file_format: FileFormat) -> "DownloadWarning":
        """Warning for files requiring conversion"""
        conversions = {
            FileFormat.RVZ: "RVZ files require Dolphin emulator to convert to ISO",
            FileFormat.WUX: "WUX files require WudCompress tool to convert to ISO/WUD"
        }
        return DownloadWarning(
            severity="info",
            message=f"File requires conversion: {conversions.get(file_format, 'Special format')}",
            suggestion="See Myrient FAQ for detailed conversion instructions",
            game_url=game_url
        )