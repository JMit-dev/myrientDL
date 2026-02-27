# MyrientDL

A robust, polite, and feature-rich downloader for the [Myrient](https://myrient.erista.me) game archive with advanced collection support, fuzzy search, resumable downloads, and integrity verification.

## What it does

MyrientDL crawls the Myrient archive, automatically categorizes games by collection (No-Intro, Redump, MAME, etc.), builds a comprehensive database, and provides powerful search and download capabilities with speed monitoring, format detection, and TorrentZip verification.

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
- `crawl` - Discover available games from Myrient archive (with collection detection)
- `search <query>` - Find games with fuzzy matching (supports --console and --collection filters)
- `collections` - List all Myrient collections with statistics
- `download` - Download games (supports --all, --console filters with speed monitoring)
- `verify` - Verify TorrentZip CRC-32 checksums for downloaded files
- `status` - Show download statistics and collection breakdown
- `list-games` - List games in database with filters

### New Collection Features

```bash
# List all collections
myrient-dl collections

# Search within a specific collection
myrient-dl search "mario" --collection "No-Intro"
myrient-dl search "final fantasy" --collection "Redump"

# Verify TorrentZip checksums
myrient-dl verify --all
```

## Supported Collections

MyrientDL supports all major Myrient collections:

| Collection | Content Type | Update Frequency |
|-----------|-------------|------------------|
| **No-Intro** | Cartridge-based systems (NES, SNES, GB, etc.) | Weekly |
| **Redump** | Optical disc systems (PS1-5, Xbox, GameCube, etc.) | Weekly |
| **MAME** | Arcade games for MAME emulator | Weekly |
| **TOSEC** | Computer software and utilities | Weekly |
| **Bitsavers** | Vintage computer software/documentation | Daily |
| **RetroAchievements** | RetroAchievements-compatible ROMs | Weekly |
| **T-En Collection** | English translation patches | Weekly |
| **And 13+ more...** | | |

## Special File Formats

MyrientDL automatically detects files that require conversion:

### RVZ Files (GameCube/Wii)
- **Format**: Dolphin's compressed format
- **Conversion**: Use Dolphin emulator to convert to ISO
- MyrientDL will warn you when downloading RVZ files

### WUX Files (Wii U)
- **Format**: Compressed Wii U disc images
- **Conversion**: Use WudCompress tool to convert to ISO/WUD
- MyrientDL will warn you when downloading WUX files

## Download Speed Monitoring

MyrientDL monitors download speeds and detects Myrient's abuse protection:

- **Normal Speed**: Full download speed (varies by connection)
- **Throttled (~10 KB/s)**: Myrient has detected potential abuse

**If throttled**, ensure you're:
1. Downloading directly from Myrient (not through third-party sites)
2. Not using browser extensions or link shorteners
3. Using supported download applications
4. Not copying/pasting links into new tabs

## Configuration

After running `init`, edit `myrient-config.yml` to customize:

- Download location
- Concurrent download limits (global and per-host)
- Rate limiting settings (token bucket algorithm)
- Timeout and retry behavior
- File type filters (include/exclude patterns)
- Checksum verification options

## Features

### Core Features
- **Collection-Aware Crawling**: Automatically detects and categorizes games by 20+ Myrient collections (No-Intro, Redump, MAME, TOSEC, Bitsavers, etc.)
- **Intelligent Search**: Fuzzy search with support for game names, consoles, regions, and collections
- **Resumable Downloads**: Pause and resume downloads with partial file support
- **Rate Limiting**: Respectful download speeds with per-host token bucket rate limiting
- **Download Speed Monitoring**: Detects Myrient's abuse protection (10 KB/s throttling) and warns users
- **TorrentZip Verification**: Verify and extract CRC-32 checksums from TorrentZipped archives
- **File Format Detection**: Identifies special formats (RVZ, WUX) that require conversion

### Advanced Features
- **Multi-Collection Support**: Browse and filter by No-Intro, Redump, MAME, TOSEC, and 16+ other collections
- **File Format Awareness**: Automatically detects file types and conversion requirements
- **Checksum Verification**: SHA-256 verification for downloaded files
- **Progress Tracking**: Real-time download progress with ETA and speed display
- **Database Persistence**: SQLite database with indexed queries for fast searching
- **Rich CLI**: Beautiful terminal UI with tables, progress bars, and colored status displays
- **Interactive Mode**: Select games from search results with range syntax (1,3,5-7)

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

GPL3.0
