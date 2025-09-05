import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path
import httpx

from myrientDL.crawler import MyrientCrawler
from myrientDL.config import MyrientConfig
from myrientDL.models import GameFile


class TestMyrientCrawler:
    
    @pytest.fixture
    def config(self):
        return MyrientConfig()
    
    @pytest.fixture
    def crawler(self, config):
        return MyrientCrawler(config)
    
    @pytest.mark.asyncio
    async def test_crawler_context_manager(self, crawler):
        """Test that crawler can be used as async context manager"""
        async with crawler:
            assert crawler.session is not None
            assert isinstance(crawler.session, httpx.AsyncClient)
    
    @pytest.mark.asyncio
    async def test_parse_directory_listing(self, crawler):
        """Test parsing of HTML directory listing"""
        # Mock HTML response that looks like Myrient's structure
        mock_html = """
        <table>
            <tr><td><a href="Super%20Mario%20World.zip">Super Mario World.zip</a></td><td>512KB</td></tr>
            <tr><td><a href="Pokemon%20Red.zip">Pokemon Red.zip</a></td><td>256KB</td></tr>
            <tr><td><a href="Nintendo%20-%20Game%20Boy/">Nintendo - Game Boy/</a></td><td>-</td></tr>
        </table>
        """
        
        from selectolax.parser import HTMLParser
        parser = HTMLParser(mock_html)
        
        base_url = "https://myrient.erista.me/files/No-Intro/"
        files, subdirs = crawler._parse_directory_listing(base_url, parser)
        
        # Should find 2 files and 1 subdirectory
        assert len(files) == 2
        assert len(subdirs) == 1
        
        # Check file details
        mario_file = next((f for f in files if "Mario" in f.name), None)
        assert mario_file is not None
        assert mario_file.name == "Super Mario World.zip"
        assert mario_file.file_type == "zip"
        
        # Check subdirectory
        assert subdirs[0] == "https://myrient.erista.me/files/No-Intro/Nintendo - Game Boy/"
    
    @pytest.mark.asyncio
    async def test_should_include_file(self, crawler):
        """Test file inclusion filtering"""
        # Test file that should be included
        game_file = GameFile(
            url="https://example.com/mario.zip",
            name="Super Mario World.zip",
            parent_path="Nintendo - SNES",
            file_type="zip"
        )
        
        assert crawler._should_include_file(game_file) == True
        
        # Test file that should be excluded (BIOS)
        bios_file = GameFile(
            url="https://example.com/bios.zip", 
            name="BIOS_file.zip",
            parent_path="System",
            file_type="zip"
        )
        
        assert crawler._should_include_file(bios_file) == False
    
    @pytest.mark.asyncio
    async def test_crawl_directory_with_mock_response(self, crawler):
        """Test crawling with mocked HTTP response"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = """
        <table>
            <tr><td><a href="Super%20Mario%20Bros.zip">Super Mario Bros.zip</a></td><td>128KB</td></tr>
        </table>
        """
        
        with patch.object(crawler, 'session') as mock_session:
            mock_session.get = AsyncMock(return_value=mock_response)
            mock_response.raise_for_status = Mock()
            
            games = []
            async for game in crawler.crawl_directory("https://example.com/"):
                games.append(game)
            
            assert len(games) == 1
            assert games[0].name == "Super Mario Bros.zip"
            assert "Mario" in games[0].name


@pytest.mark.asyncio 
async def test_real_myrient_connection():
    """Test actual connection to Myrient (integration test)"""
    config = MyrientConfig()
    
    async with MyrientCrawler(config) as crawler:
        try:
            # Test just fetching the main page
            response = await crawler.session.get("https://myrient.erista.me/files/")
            assert response.status_code == 200
            
            # Check if we get some expected content
            content = response.text.lower()
            assert "myrient" in content or "directory" in content or "table" in content
            
        except httpx.RequestError:
            pytest.skip("Cannot connect to Myrient - network issue")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])