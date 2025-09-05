"""
MyrientDL - A polite, resumable downloader for Myrient game archive

This package provides a comprehensive client for downloading games from Myrient
with features like fuzzy search, rate limiting, resumable downloads, and more.
"""

__version__ = "0.1.0"
__author__ = "Jordan Mitacek"

from .config import MyrientConfig
from .models import GameFile, DownloadStatus, DownloadStats
from .database import Database
from .crawler import MyrientCrawler
from .downloader import DownloadManager
from .search import GameSearch, SearchResult

__all__ = [
    "MyrientConfig",
    "GameFile", 
    "DownloadStatus",
    "DownloadStats", 
    "Database",
    "MyrientCrawler",
    "DownloadManager",
    "GameSearch",
    "SearchResult",
]