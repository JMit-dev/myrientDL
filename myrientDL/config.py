from pydantic import BaseModel, Field
from typing import List, Optional
from pathlib import Path


class ConcurrencyConfig(BaseModel):
    global_max: int = Field(
        default=8, description="Maximum concurrent downloads globally"
    )
    per_host: int = Field(
        default=3, description="Maximum concurrent downloads per host"
    )


class RateLimitConfig(BaseModel):
    tokens_per_sec: float = Field(default=1.0, description="Tokens per second per host")
    burst: int = Field(default=3, description="Maximum burst tokens")


class TimeoutConfig(BaseModel):
    connect: int = Field(default=10, description="Connection timeout in seconds")
    read: int = Field(default=120, description="Read timeout in seconds")


class RetryConfig(BaseModel):
    max_attempts: int = Field(default=3, description="Maximum retry attempts")
    backoff_base: float = Field(default=1.0, description="Base backoff time in seconds")
    backoff_cap: float = Field(
        default=30.0, description="Maximum backoff time in seconds"
    )


class MyrientConfig(BaseModel):
    user_agent: str = Field(
        default="MyrientDL/1.0 (Educational/Archival Use)",
        description="User agent string",
    )
    download_root: Path = Field(
        default=Path("./downloads"), description="Root directory for downloads"
    )
    database_path: Path = Field(
        default=Path("./myrient.db"), description="SQLite database path"
    )
    base_url: str = Field(
        default="https://myrient.erista.me/files/", description="Base URL for Myrient"
    )

    concurrency: ConcurrencyConfig = Field(default_factory=ConcurrencyConfig)
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)
    timeouts: TimeoutConfig = Field(default_factory=TimeoutConfig)
    retries: RetryConfig = Field(default_factory=RetryConfig)

    # Search and filter options
    include_patterns: List[str] = Field(
        default=["*.zip", "*.7z", "*.rar", "*.iso", "*.wbfs", "*.rvz", "*.wux"],
        description="File patterns to include",
    )
    exclude_patterns: List[str] = Field(
        default=["*BIOS*", "*bios*", "*System*"], description="File patterns to exclude"
    )

    # Download behavior
    verify_checksums: bool = Field(
        default=True, description="Verify file checksums when available"
    )
    resume_downloads: bool = Field(default=True, description="Resume partial downloads")
    max_download_size: Optional[int] = Field(
        default=None,
        description="Maximum file size to download in bytes (None for no limit)",
    )

    class Config:
        json_encoders = {Path: str}
