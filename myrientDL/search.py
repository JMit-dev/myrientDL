from typing import List, Optional, Dict, Any, Tuple
import re
from fuzzywuzzy import fuzz, process
from dataclasses import dataclass

from .models import GameFile, Collection
from .database import Database


@dataclass
class SearchResult:
    game_file: GameFile
    score: int
    match_type: str  # "exact", "fuzzy", "partial"
    matched_field: str  # "name", "console", "region"


class GameSearch:
    def __init__(self, database: Database):
        self.database = database
        
        # Common game name patterns and abbreviations
        self.name_normalizations = {
            "pokemon": ["pokémon", "pocket monsters"],
            "zelda": ["legend of zelda", "tloz"],
            "mario": ["super mario", "mario bros"],
            "street fighter": ["sf", "streetfighter"],
            "final fantasy": ["ff"],
            "dragon quest": ["dq", "dragon warrior"],
            "metroid": ["super metroid"],
            "castlevania": ["akumajou dracula"],
            "resident evil": ["biohazard"],
            "tekken": ["tekken force"],
        }
        
        # Console name variations
        self.console_aliases = {
            "gb": ["game boy", "gameboy"],
            "gba": ["game boy advance", "gameboy advance"],
            "gbc": ["game boy color", "gameboy color"],
            "ds": ["nintendo ds", "nds"],
            "3ds": ["nintendo 3ds", "n3ds"],
            "nes": ["nintendo entertainment system", "famicom"],
            "snes": ["super nintendo", "super famicom", "sfc"],
            "n64": ["nintendo 64"],
            "gc": ["gamecube", "nintendo gamecube"],
            "wii": ["nintendo wii"],
            "wiiu": ["wii u", "nintendo wii u"],
            "switch": ["nintendo switch", "ns"],
            "ps1": ["playstation", "psx"],
            "ps2": ["playstation 2"],
            "ps3": ["playstation 3"],
            "ps4": ["playstation 4"],
            "ps5": ["playstation 5"],
            "psp": ["playstation portable"],
            "vita": ["ps vita", "playstation vita", "psvita"],
            "xbox": ["microsoft xbox"],
            "x360": ["xbox 360"],
            "xone": ["xbox one"],
            "genesis": ["mega drive", "sega genesis", "sega mega drive"],
            "saturn": ["sega saturn"],
            "dreamcast": ["sega dreamcast"],
        }
    
    async def search(
        self,
        query: str,
        console: Optional[str] = None,
        collection: Optional[Collection] = None,
        limit: int = 50,
        min_score: int = 60
    ) -> List[SearchResult]:
        """
        Perform fuzzy search for games

        Args:
            query: Search query (game name, partial name, etc.)
            console: Filter by console (optional)
            collection: Filter by collection (optional)
            limit: Maximum number of results
            min_score: Minimum fuzzy match score (0-100)
        """
        results = []

        # Get all games (filtered by console if specified)
        all_games = await self.database.get_game_files(console=console, limit=None)

        # Filter by collection if specified
        if collection:
            all_games = [g for g in all_games if g.collection == collection]

        if not all_games:
            return results

        # Normalize query
        normalized_query = self._normalize_text(query)

        # Try different search strategies
        results.extend(await self._exact_search(normalized_query, all_games))
        results.extend(await self._fuzzy_search(normalized_query, all_games, min_score))
        results.extend(await self._partial_search(normalized_query, all_games, min_score))
        results.extend(await self._console_search(query, all_games))
        results.extend(await self._region_search(query, all_games))
        results.extend(await self._collection_search(query, all_games))

        # Remove duplicates and sort by score
        unique_results = {}
        for result in results:
            url = result.game_file.url
            if url not in unique_results or result.score > unique_results[url].score:
                unique_results[url] = result
        
        # Sort by score (descending) and take top results
        sorted_results = sorted(unique_results.values(), key=lambda x: x.score, reverse=True)
        return sorted_results[:limit]
    
    async def _exact_search(self, query: str, games: List[GameFile]) -> List[SearchResult]:
        """Find exact matches"""
        results = []
        
        for game in games:
            normalized_name = self._normalize_text(game.name)
            
            if query == normalized_name:
                results.append(SearchResult(
                    game_file=game,
                    score=100,
                    match_type="exact",
                    matched_field="name"
                ))
        
        return results
    
    async def _fuzzy_search(self, query: str, games: List[GameFile], min_score: int) -> List[SearchResult]:
        """Perform fuzzy string matching on game names"""
        results = []
        
        # Create list of (normalized_name, game) tuples
        game_names = [(self._normalize_text(game.name), game) for game in games]
        
        # Use fuzzywuzzy to find best matches
        matches = process.extract(
            query,
            [name for name, _ in game_names],
            scorer=fuzz.ratio,
            limit=len(game_names)
        )
        
        # Create name-to-game mapping
        name_to_game = {name: game for name, game in game_names}
        
        for match_name, score in matches:
            if score >= min_score:
                game = name_to_game[match_name]
                results.append(SearchResult(
                    game_file=game,
                    score=score,
                    match_type="fuzzy",
                    matched_field="name"
                ))
        
        return results
    
    async def _partial_search(self, query: str, games: List[GameFile], min_score: int) -> List[SearchResult]:
        """Find partial matches using substring search"""
        results = []
        
        for game in games:
            normalized_name = self._normalize_text(game.name)
            
            if query in normalized_name:
                # Calculate score based on how much of the name matches
                score = min(95, int((len(query) / len(normalized_name)) * 100))
                
                if score >= min_score:
                    results.append(SearchResult(
                        game_file=game,
                        score=score,
                        match_type="partial",
                        matched_field="name"
                    ))
        
        return results
    
    async def _console_search(self, query: str, games: List[GameFile]) -> List[SearchResult]:
        """Search by console name"""
        results = []
        normalized_query = self._normalize_text(query)
        
        # Check if query matches a console
        for game in games:
            if game.console:
                normalized_console = self._normalize_text(game.console)
                
                # Check direct match
                if normalized_query == normalized_console:
                    results.append(SearchResult(
                        game_file=game,
                        score=90,
                        match_type="exact",
                        matched_field="console"
                    ))
                
                # Check console aliases
                for alias, variations in self.console_aliases.items():
                    if (normalized_query == alias or 
                        any(normalized_query == self._normalize_text(var) for var in variations)):
                        if normalized_console in [self._normalize_text(var) for var in variations]:
                            results.append(SearchResult(
                                game_file=game,
                                score=85,
                                match_type="fuzzy",
                                matched_field="console"
                            ))
        
        return results
    
    async def _region_search(self, query: str, games: List[GameFile]) -> List[SearchResult]:
        """Search by region"""
        results = []
        normalized_query = self._normalize_text(query)

        region_keywords = ["usa", "europe", "japan", "world", "en", "fr", "de", "es", "it"]

        if any(keyword in normalized_query for keyword in region_keywords):
            for game in games:
                if game.region:
                    normalized_region = self._normalize_text(game.region)

                    if normalized_query in normalized_region or normalized_region in normalized_query:
                        results.append(SearchResult(
                            game_file=game,
                            score=75,
                            match_type="partial",
                            matched_field="region"
                        ))

        return results

    async def _collection_search(self, query: str, games: List[GameFile]) -> List[SearchResult]:
        """Search by collection name"""
        results = []
        normalized_query = self._normalize_text(query)

        collection_keywords = {
            "no-intro": Collection.NO_INTRO,
            "nointro": Collection.NO_INTRO,
            "redump": Collection.REDUMP,
            "mame": Collection.MAME,
            "tosec": Collection.TOSEC,
            "arcade": [Collection.MAME, Collection.FBNEO, Collection.TEKNOPARROT],
        }

        for keyword, collection in collection_keywords.items():
            if keyword in normalized_query:
                collections = [collection] if isinstance(collection, Collection) else collection
                for game in games:
                    if game.collection in collections:
                        results.append(SearchResult(
                            game_file=game,
                            score=70,
                            match_type="partial",
                            matched_field="collection"
                        ))

        return results
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison"""
        if not text:
            return ""
        
        # Convert to lowercase
        text = text.lower()
        
        # Remove common separators and punctuation
        text = re.sub(r'[_\-\.\(\)\[\]!]', ' ', text)
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        # Apply name normalizations
        for normalized, variations in self.name_normalizations.items():
            for variation in variations:
                if variation in text:
                    text = text.replace(variation, normalized)
        
        return text
    
    async def get_search_suggestions(self, partial_query: str, limit: int = 10) -> List[str]:
        """Get search suggestions based on partial input"""
        if len(partial_query) < 2:
            return []
        
        suggestions = set()
        
        # Get games from database
        games = await self.database.get_game_files(limit=1000)
        
        normalized_query = self._normalize_text(partial_query)
        
        for game in games:
            normalized_name = self._normalize_text(game.name)
            
            # Add game names that start with the query
            if normalized_name.startswith(normalized_query):
                # Extract the main title (before parentheses/brackets)
                clean_name = re.split(r'[\(\[\-]', game.name)[0].strip()
                suggestions.add(clean_name)
            
            # Add console names
            if game.console and self._normalize_text(game.console).startswith(normalized_query):
                suggestions.add(game.console)
        
        return sorted(list(suggestions))[:limit]
    
    async def get_popular_games(self, console: Optional[str] = None, limit: int = 20) -> List[GameFile]:
        """Get popular/recommended games (simplified heuristic)"""
        games = await self.database.get_game_files(console=console, limit=None)
        
        # Simple popularity heuristic based on common keywords
        popular_keywords = [
            "super", "legend", "final", "street", "pokemon", "zelda", "mario",
            "sonic", "metroid", "castlevania", "dragon", "resident", "mega",
            "ultimate", "championship", "deluxe", "complete", "goty"
        ]
        
        scored_games = []
        for game in games:
            score = 0
            name_lower = game.name.lower()
            
            # Award points for popular keywords
            for keyword in popular_keywords:
                if keyword in name_lower:
                    score += 10
            
            # Prefer certain file types
            if game.file_type in ["zip", "7z"]:
                score += 5
            
            # Prefer certain regions (English-friendly)
            if game.region and any(region in game.region.lower() for region in ["usa", "world", "en"]):
                score += 15
            
            scored_games.append((score, game))
        
        # Sort by score and return top games
        scored_games.sort(key=lambda x: x[0], reverse=True)
        return [game for _, game in scored_games[:limit]]