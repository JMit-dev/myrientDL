# MyrientDL

A polite, resumable downloader for the Myrient game archive with search capabilities.

## What it does

MyrientDL crawls the Myrient archive, builds a local database of available games, and lets you search and download them with resumable downloads and rate limiting to be respectful to the servers.

## Installation

1. Clone this repository
2. Install with pip:
   ```bash
   pip install -e .
   ```

Then use with:
```bash
python -m myrientDL.cli --help
```

Requires Python 3.9+

## Basic Usage

1. **Initialize project**:
   ```bash
   myrient-dl init
   ```

2. **Discover games** (takes a while first time):
   ```bash
   myrient-dl crawl
   ```

3. **Search for games**:
   ```bash
   myrient-dl search "mario"
   myrient-dl search "pokemon" --console "Game Boy"
   ```

4. **Download games**:
   ```bash
   myrient-dl download --all
   myrient-dl download --console "Nintendo - Game Boy"
   ```

5. **Check status**:
   ```bash
   myrient-dl status
   myrient-dl list-games
   ```

## Commands

- `init` - Set up a project directory with config and database
- `crawl` - Discover available games from Myrient archive  
- `search <query>` - Find games with fuzzy matching
- `download` - Download games (supports --all, --console filters)
- `status` - Show download statistics
- `list-games` - List games in database with filters

## Configuration

After running `init`, edit `myrient-config.yml` to customize:
- Download location
- Concurrent download limits  
- Rate limiting settings
- File type filters

## Features

- Smart fuzzy search with game name normalization
- Resumable downloads that continue where they left off
- Per-host rate limiting to be polite to servers
- Progress tracking with rich terminal output
- SQLite database for persistent game tracking
- Console-based filtering (Game Boy, SNES, etc.)
- Interactive game selection from search results

## Example Workflow

```bash
# Set up
mkdir my-games && cd my-games
myrient-dl init

# Discover what's available
myrient-dl crawl

# Find and download games
myrient-dl search "zelda" --interactive
myrient-dl download --console "Nintendo - Game Boy Advance"

# Monitor progress  
myrient-dl status
```

## License

MIT