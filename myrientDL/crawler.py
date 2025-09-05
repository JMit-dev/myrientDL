import asyncio
import re
from typing import List, Set, Optional, AsyncGenerator
from urllib.parse import urljoin, urlparse, unquote
from pathlib import Path
import fnmatch
from datetime import datetime

import httpx
from selectolax.parser import HTMLParser

from .models import GameFile, CrawlResult, DownloadStatus
from .config import MyrientConfig


class MyrientCrawler:
    def __init__(self, config: MyrientConfig):
        self.config = config
        self.session: Optional[httpx.AsyncClient] = None
        self.visited_urls: Set[str] = set()
        
        # Regex patterns for extracting game info
        self.region_patterns = [
            r'\(([^)]*(?:USA|Europe|Japan|World|En|Fr|De|Es|It|Pt|Nl|Sv|No|Da|Fi|Ru|Ko|Zh|Rev \d+)[^)]*)\)',
            r'\[([^\]]*(?:USA|Europe|Japan|World|En|Fr|De|Es|It|Pt|Nl|Sv|No|Da|Fi|Ru|Ko|Zh|Rev \d+)[^\]]*)\]'
        ]
    
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
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.aclose()
    
    async def crawl_directory(self, url: str, max_depth: int = 3) -> AsyncGenerator[GameFile, None]:
        """Crawl a directory and yield GameFile objects"""
        if url in self.visited_urls or max_depth <= 0:
            return
        
        self.visited_urls.add(url)
        
        try:
            response = await self.session.get(url)
            response.raise_for_status()
            
            parser = HTMLParser(response.text)
            
            # Extract files and subdirectories
            files, subdirs = self._parse_directory_listing(url, parser)
            
            # Yield files that match our criteria
            for file_info in files:
                if self._should_include_file(file_info):
                    yield file_info
            
            # Recursively crawl subdirectories
            for subdir_url in subdirs:
                async for game_file in self.crawl_directory(subdir_url, max_depth - 1):
                    yield game_file
                    
        except Exception as e:
            print(f"Error crawling {url}: {e}")
    
    def _parse_directory_listing(self, base_url: str, parser: HTMLParser) -> tuple[List[GameFile], List[str]]:
        """Parse HTML directory listing to extract files and subdirectories"""
        files = []
        subdirs = []
        
        # Look for table rows or file listings
        # Myrient uses a table format for file listings
        rows = parser.css("tr")
        
        for row in rows:
            cells = row.css("td")
            if len(cells) < 2:
                continue
            
            # First cell usually contains the link
            link_cell = cells[0]
            link_elem = link_cell.css_first("a")
            
            if not link_elem:
                continue
            
            href = link_elem.attributes.get("href", "")
            if not href or href.startswith("?") or href == "../":
                continue
            
            full_url = urljoin(base_url, href)
            filename = unquote(href.rstrip("/"))
            
            # Check if it's a directory (ends with /) or file
            if href.endswith("/"):
                subdirs.append(full_url)
            else:
                # Extract file size (usually in second or third cell)
                size = None
                for cell in cells[1:]:
                    size_text = cell.text().strip()
                    if size_text and size_text != "-":
                        size = self._parse_file_size(size_text)
                        break
                
                # Create GameFile object
                game_file = GameFile(
                    url=full_url,
                    name=filename,
                    size=size,
                    parent_path=self._extract_parent_path(base_url),
                    file_type=Path(filename).suffix.lstrip('.').lower(),
                    console=self._extract_console(base_url),
                    region=self._extract_region(filename)
                )
                
                files.append(game_file)
        
        return files, subdirs
    
    def _should_include_file(self, game_file: GameFile) -> bool:
        """Check if file should be included based on patterns"""
        filename = game_file.name
        
        # Check include patterns
        if self.config.include_patterns:
            if not any(fnmatch.fnmatch(filename, pattern) for pattern in self.config.include_patterns):
                return False
        
        # Check exclude patterns
        if self.config.exclude_patterns:
            if any(fnmatch.fnmatch(filename, pattern) for pattern in self.config.exclude_patterns):
                return False
        
        # Check file size limit
        if self.config.max_download_size and game_file.size:
            if game_file.size > self.config.max_download_size:
                return False
        
        return True
    
    def _parse_file_size(self, size_text: str) -> Optional[int]:
        """Parse file size string to bytes"""
        size_text = size_text.strip().replace(",", "")
        
        # Handle different size formats
        multipliers = {
            'B': 1,
            'KB': 1024,
            'MB': 1024**2,
            'GB': 1024**3,
            'TB': 1024**4,
            'K': 1024,
            'M': 1024**2,
            'G': 1024**3,
        }
        
        # Try to match pattern like "123.45 MB" or "123KB"
        match = re.match(r'(\d+(?:\.\d+)?)\s*([KMGT]?B?)', size_text.upper())
        if match:
            size_value = float(match.group(1))
            unit = match.group(2) or 'B'
            return int(size_value * multipliers.get(unit, 1))
        
        # Try to parse as plain number
        try:
            return int(size_text)
        except ValueError:
            return None
    
    def _extract_parent_path(self, url: str) -> str:
        """Extract parent path from URL for categorization"""
        parsed = urlparse(url)
        path = parsed.path.rstrip('/')
        
        # Remove base path
        base_path = urlparse(self.config.base_url).path.rstrip('/')
        if path.startswith(base_path):
            path = path[len(base_path):].lstrip('/')
        
        return path
    
    def _extract_console(self, url: str) -> Optional[str]:
        """Extract console name from URL path"""
        parent_path = self._extract_parent_path(url)
        
        # Common patterns in Myrient paths
        console_mappings = {
            "nintendo - game boy": "Game Boy",
            "nintendo - game boy advance": "Game Boy Advance",
            "nintendo - game boy color": "Game Boy Color",
            "nintendo - nintendo ds": "Nintendo DS",
            "nintendo - nintendo 3ds": "Nintendo 3DS",
            "nintendo - nintendo entertainment system": "NES",
            "nintendo - super nintendo entertainment system": "SNES",
            "nintendo - nintendo 64": "Nintendo 64",
            "nintendo - nintendo gamecube": "GameCube",
            "nintendo - wii": "Wii",
            "nintendo - wii u": "Wii U",
            "nintendo - switch": "Nintendo Switch",
            "sony - playstation": "PlayStation",
            "sony - playstation 2": "PlayStation 2",
            "sony - playstation 3": "PlayStation 3",
            "sony - playstation 4": "PlayStation 4",
            "sony - playstation portable": "PSP",
            "sony - playstation vita": "PS Vita",
            "sega - master system": "Master System",
            "sega - mega drive - genesis": "Genesis/Mega Drive",
            "sega - game gear": "Game Gear",
            "sega - saturn": "Saturn",
            "sega - dreamcast": "Dreamcast",
            "microsoft - xbox": "Xbox",
            "microsoft - xbox 360": "Xbox 360",
            "microsoft - xbox one": "Xbox One",
            "atari - 2600": "Atari 2600",
            "atari - 7800": "Atari 7800",
        }
        
        parent_lower = parent_path.lower()
        for key, value in console_mappings.items():
            if key in parent_lower:
                return value
        
        # Try to extract from path segments
        segments = parent_path.split('/')
        for segment in segments:
            if any(console_name in segment.lower() for console_name in 
                   ["nintendo", "sony", "sega", "microsoft", "atari", "game boy", "playstation"]):
                return segment.replace(' - ', ' ').title()
        
        return None
    
    def _extract_region(self, filename: str) -> Optional[str]:
        """Extract region information from filename"""
        for pattern in self.region_patterns:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                return match.group(1)
        return None
    
    async def get_robots_txt(self, base_url: str) -> Optional[str]:
        """Fetch robots.txt for the domain"""
        try:
            robots_url = urljoin(base_url, "/robots.txt")
            response = await self.session.get(robots_url)
            if response.status_code == 200:
                return response.text
        except Exception:
            pass
        return None