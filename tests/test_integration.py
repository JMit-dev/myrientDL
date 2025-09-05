import pytest
import asyncio
from pathlib import Path

from myrientDL.crawler import MyrientCrawler
from myrientDL.config import MyrientConfig


@pytest.mark.asyncio
async def test_myrient_structure():
    """Test to understand Myrient's actual HTML structure"""
    config = MyrientConfig()
    
    async with MyrientCrawler(config) as crawler:
        try:
            # Get main page
            response = await crawler.session.get("https://myrient.erista.me/files/")
            print(f"\nStatus: {response.status_code}")
            print(f"Content length: {len(response.text)}")
            
            # Parse with our current logic
            from selectolax.parser import HTMLParser
            parser = HTMLParser(response.text)
            
            files, subdirs = crawler._parse_directory_listing("https://myrient.erista.me/files/", parser)
            
            print(f"Our parser found: {len(files)} files, {len(subdirs)} subdirs")
            print("Subdirs found:")
            for subdir in subdirs:
                print(f"  - {subdir}")
            
            # Now try going deeper - test No-Intro which should have Nintendo systems
            if subdirs:
                nointro_url = next((d for d in subdirs if "No-Intro" in d), None)
                if nointro_url:
                    print(f"\nTesting No-Intro directory: {nointro_url}")
                    response2 = await crawler.session.get(nointro_url)
                    parser2 = HTMLParser(response2.text)
                    files2, subdirs2 = crawler._parse_directory_listing(nointro_url, parser2)
                    
                    print(f"No-Intro has: {len(files2)} files, {len(subdirs2)} subdirs")
                    # Find Game Boy and Mario-related directories
                    gameboy_dirs = [d for d in subdirs2 if "game boy" in d.lower()]
                    mario_dirs = [d for d in subdirs2 if "mario" in d.lower()]
                    nintendo_dirs = [d for d in subdirs2 if "nintendo" in d.lower()]
                    
                    print(f"Game Boy directories: {len(gameboy_dirs)}")
                    for nd in gameboy_dirs:
                        print(f"  - {nd}")
                    
                    print(f"Mario directories: {len(mario_dirs)}")  
                    for nd in mario_dirs:
                        print(f"  - {nd}")
                        
                    print(f"Nintendo directories (first 10): {len(nintendo_dirs)}")
                    for nd in nintendo_dirs[:10]:
                        print(f"  - {nd}")
                    
                    # Look for the actual Game Boy directory (should have Mario games)
                    gameboy_dir = next((d for d in subdirs2 if "Nintendo%20-%20Game%20Boy/" in d and "Advance" not in d and "Aftermarket" not in d and "Private" not in d), None)
                    print(f"Found Game Boy directory: {gameboy_dir}")
                    if gameboy_dir:
                        nintendo_dirs = [gameboy_dir]
                        print(f"Updated nintendo_dirs to: {nintendo_dirs}")
                    
                    # Try one Nintendo directory
                    if nintendo_dirs:
                        test_dir = nintendo_dirs[0]
                        print(f"\nTesting Nintendo directory: {test_dir}")
                        response3 = await crawler.session.get(test_dir)
                        parser3 = HTMLParser(response3.text)
                        files3, subdirs3 = crawler._parse_directory_listing(test_dir, parser3)
                        
                        print(f"Nintendo dir has: {len(files3)} files, {len(subdirs3)} subdirs")
                        
                        # Look for Mario games specifically  
                        mario_games = [f for f in files3 if "mario" in f.name.lower()]
                        print(f"Mario games found: {len(mario_games)}")
                        for game in mario_games:
                            print(f"  [MARIO] {game.name} ({game.file_type})")
                        
                        print("Other games:")
                        other_games = [f for f in files3 if "mario" not in f.name.lower()]
                        for game in other_games[:5]:
                            print(f"  - {game.name} ({game.file_type})")
            
        except Exception as e:
            print(f"Error: {e}")
            raise


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])