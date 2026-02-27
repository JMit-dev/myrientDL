"""
API Models for FastAPI

Pydantic models for request/response validation.
"""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class GameFileResponse(BaseModel):
    id: int
    url: str
    name: str
    size: Optional[int]
    console: Optional[str]
    region: Optional[str]
    collection: str
    file_format: Optional[str]
    requires_conversion: bool
    status: str
    bytes_downloaded: int
    download_progress: float
    formatted_size: str

    class Config:
        from_attributes = True


class CollectionResponse(BaseModel):
    name: str
    game_count: int
    total_size: int
    update_frequency: str
    content_type: str


class SearchRequest(BaseModel):
    query: str
    console: Optional[str] = None
    collection: Optional[str] = None
    limit: Optional[int] = 50


class DownloadRequest(BaseModel):
    game_ids: List[int]


class StatsResponse(BaseModel):
    total_games: int
    total_size: int
    downloaded_games: int
    downloaded_size: int
    pending_games: int
    failed_games: int
    collections_count: int
    consoles_count: int


class CrawlStatus(BaseModel):
    is_running: bool
    games_found: int
    last_crawl: Optional[datetime]
    current_url: Optional[str]
    progress_percentage: float
