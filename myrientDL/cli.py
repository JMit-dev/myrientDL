import asyncio
import sys
from typing import Optional, List
from pathlib import Path
import yaml

import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, TaskID, BarColumn, TextColumn, TimeRemainingColumn
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.text import Text

from .config import MyrientConfig
from .database import Database
from .crawler import MyrientCrawler
from .downloader import DownloadManager
from .search import GameSearch, SearchResult
from .models import GameFile, DownloadStatus

app = typer.Typer(name="myrient-dl", help="A polite, resumable downloader for Myrient game archive")
console = Console()


def load_config(config_path: Optional[Path] = None) -> MyrientConfig:
    """Load configuration from file or use defaults"""
    if config_path and config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
            return MyrientConfig(**config_data)
    return MyrientConfig()


def save_config(config: MyrientConfig, config_path: Path):
    """Save configuration to file"""
    config_dict = config.model_dump()
    config_dict['download_root'] = str(config_dict['download_root'])
    config_dict['database_path'] = str(config_dict['database_path'])
    
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config_dict, f, default_flow_style=False, indent=2)


@app.command()
def init(
    directory: Optional[Path] = typer.Argument(None, help="Directory to initialize (default: current)"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing configuration")
):
    """Initialize a new myrient-dl project"""
    if directory is None:
        directory = Path.cwd()
    
    directory.mkdir(parents=True, exist_ok=True)
    config_path = directory / "myrient-config.yml"
    
    if config_path.exists() and not force:
        console.print(f"[red]Configuration already exists at {config_path}[/red]")
        console.print("Use --force to overwrite")
        raise typer.Exit(1)
    
    # Create default config
    config = MyrientConfig()
    config.download_root = directory / "downloads"
    config.database_path = directory / "myrient.db"
    
    save_config(config, config_path)
    console.print(f"[green]Initialized myrient-dl project in {directory}[/green]")
    console.print(f"Configuration saved to {config_path}")


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query (game name, console, etc.)"),
    console_filter: Optional[str] = typer.Option(None, "--console", "-c", help="Filter by console"),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum number of results"),
    config_path: Optional[Path] = typer.Option(None, "--config", help="Configuration file path"),
    interactive: bool = typer.Option(True, "--interactive/--no-interactive", help="Interactive selection mode")
):
    """Search for games in the Myrient archive"""
    asyncio.run(search_command(query, console_filter, limit, config_path, interactive))


async def search_command(
    query: str, 
    console_filter: Optional[str], 
    limit: int, 
    config_path: Optional[Path],
    interactive: bool
):
    config = load_config(config_path)
    
    async with Database(config.database_path) as db:
        await db.init_db()
        search_engine = GameSearch(db)
        
        # Check if we have any games in database
        all_games = await db.get_game_files(limit=1)
        if not all_games:
            console.print("[yellow]No games found in database. Run 'myrient-dl crawl' first.[/yellow]")
            return
        
        results = await search_engine.search(query, console_filter, limit)
        
        if not results:
            console.print(f"[red]No results found for '{query}'[/red]")
            
            # Suggest similar queries
            suggestions = await search_engine.get_search_suggestions(query, 5)
            if suggestions:
                console.print("\nDid you mean:")
                for suggestion in suggestions:
                    console.print(f"  • {suggestion}")
            return
        
        # Display results
        table = Table(title=f"Search Results for '{query}'")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Game", style="white")
        table.add_column("Console", style="green")
        table.add_column("Size", style="yellow")
        table.add_column("Score", style="blue")
        table.add_column("Status", style="magenta")
        
        for i, result in enumerate(results, 1):
            game = result.game_file
            size_mb = f"{game.size_mb:.1f} MB" if game.size else "Unknown"
            status_color = {
                DownloadStatus.COMPLETED: "green",
                DownloadStatus.DOWNLOADING: "blue",
                DownloadStatus.FAILED: "red",
                DownloadStatus.PENDING: "white"
            }.get(game.status, "white")
            
            table.add_row(
                str(i),
                game.name[:50] + "..." if len(game.name) > 50 else game.name,
                game.console or "Unknown",
                size_mb,
                str(result.score),
                f"[{status_color}]{game.status.value}[/{status_color}]"
            )
        
        console.print(table)
        
        if interactive:
            # Interactive selection
            selections = Prompt.ask(
                "Select games to download (e.g., 1,3,5-7) or 'all'",
                default="none"
            )
            
            if selections.lower() == "none":
                return
            
            selected_games = []
            if selections.lower() == "all":
                selected_games = [result.game_file for result in results]
            else:
                indices = parse_selection(selections, len(results))
                selected_games = [results[i-1].game_file for i in indices]
            
            if selected_games:
                await download_games(selected_games, config)


def parse_selection(selection_str: str, max_index: int) -> List[int]:
    """Parse selection string like '1,3,5-7' into list of indices"""
    indices = []
    parts = selection_str.split(',')
    
    for part in parts:
        part = part.strip()
        if '-' in part:
            start, end = map(int, part.split('-'))
            indices.extend(range(start, min(end + 1, max_index + 1)))
        else:
            idx = int(part)
            if 1 <= idx <= max_index:
                indices.append(idx)
    
    return sorted(set(indices))


@app.command()
def crawl(
    url: Optional[str] = typer.Option(None, help="Specific URL to crawl (default: full Myrient archive)"),
    max_depth: int = typer.Option(3, "--depth", "-d", help="Maximum crawl depth"),
    config_path: Optional[Path] = typer.Option(None, "--config", help="Configuration file path"),
    update: bool = typer.Option(False, "--update", "-u", help="Update existing entries")
):
    """Crawl Myrient archive to discover games"""
    asyncio.run(crawl_command(url, max_depth, config_path, update))


async def crawl_command(url: Optional[str], max_depth: int, config_path: Optional[Path], update: bool):
    config = load_config(config_path)
    crawl_url = url or config.base_url
    
    async with Database(config.database_path) as db:
        await db.init_db()
        
        console.print(f"[blue]Starting crawl of {crawl_url}[/blue]")
        
        discovered_count = 0
        added_count = 0
        
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("•"),
            TextColumn("[blue]{task.completed}[/blue] games found")
        ) as progress:
            task = progress.add_task("Crawling...", total=None)
            
            async with MyrientCrawler(config) as crawler:
                async for game_file in crawler.crawl_directory(crawl_url, max_depth):
                    discovered_count += 1
                    progress.update(task, completed=discovered_count)
                    
                    # Add to database
                    was_added = await db.add_game_file(game_file)
                    if was_added:
                        added_count += 1
                    elif update:
                        await db.update_game_file(game_file)
        
        console.print(f"[green]Crawl complete![/green]")
        console.print(f"Discovered: {discovered_count} games")
        console.print(f"Added to database: {added_count} new games")


@app.command()
def download(
    game_ids: Optional[List[str]] = typer.Argument(None, help="Game IDs or URLs to download"),
    all_pending: bool = typer.Option(False, "--all", help="Download all pending games"),
    console_filter: Optional[str] = typer.Option(None, "--console", "-c", help="Download all games for console"),
    config_path: Optional[Path] = typer.Option(None, "--config", help="Configuration file path"),
    concurrent: int = typer.Option(None, "--concurrent", help="Override concurrent downloads limit")
):
    """Download games"""
    asyncio.run(download_command(game_ids, all_pending, console_filter, config_path, concurrent))


async def download_command(
    game_ids: Optional[List[str]], 
    all_pending: bool, 
    console_filter: Optional[str],
    config_path: Optional[Path],
    concurrent: Optional[int]
):
    config = load_config(config_path)
    
    if concurrent:
        config.concurrency.global_max = concurrent
    
    async with Database(config.database_path) as db:
        await db.init_db()
        
        # Determine which games to download
        games_to_download = []
        
        if all_pending:
            games_to_download = await db.get_game_files(status=DownloadStatus.PENDING)
        elif console_filter:
            games_to_download = await db.get_game_files(console=console_filter, status=DownloadStatus.PENDING)
        elif game_ids:
            for game_id in game_ids:
                if game_id.startswith("http"):
                    game = await db.get_game_file(game_id)
                else:
                    # Assume it's a search term
                    search_engine = GameSearch(db)
                    results = await search_engine.search(game_id, limit=1)
                    game = results[0].game_file if results else None
                
                if game:
                    games_to_download.append(game)
        else:
            console.print("[red]No games specified. Use --all, --console, or provide game IDs[/red]")
            return
        
        if not games_to_download:
            console.print("[yellow]No games to download[/yellow]")
            return
        
        console.print(f"[blue]Downloading {len(games_to_download)} games...[/blue]")
        await download_games(games_to_download, config)


async def download_games(games: List[GameFile], config: MyrientConfig):
    """Download a list of games with progress display"""
    total_size = sum(game.size or 0 for game in games)
    
    async with Database(config.database_path) as db:
        async with DownloadManager(config, db) as manager:
            progress_data = {}
            
            with Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.1f}%"),
                TextColumn("•"),
                TextColumn("[blue]{task.completed}/{task.total}[/blue]"),
                TimeRemainingColumn()
            ) as progress:
                
                # Create progress tasks for each game
                for game in games:
                    task_id = progress.add_task(
                        game.name[:30] + "..." if len(game.name) > 30 else game.name,
                        total=game.size or 100,
                        completed=game.bytes_downloaded
                    )
                    progress_data[game.url] = task_id
                
                # Add progress callback
                def update_progress(game_file: GameFile, downloaded: int, total: int):
                    if game_file.url in progress_data:
                        task_id = progress_data[game_file.url]
                        progress.update(task_id, completed=downloaded, total=total or 100)
                
                manager.add_progress_callback(update_progress)
                
                # Start downloads
                results = await manager.download_batch(games)
                
                console.print("\n[green]Download Summary:[/green]")
                console.print(f"  Successful: {results['successful']}")
                console.print(f"  Failed: {results['failed']}")
                console.print(f"  Skipped: {results['skipped']}")


@app.command()
def status(
    config_path: Optional[Path] = typer.Option(None, "--config", help="Configuration file path")
):
    """Show download status and statistics"""
    asyncio.run(status_command(config_path))


async def status_command(config_path: Optional[Path]):
    config = load_config(config_path)
    
    async with Database(config.database_path) as db:
        await db.init_db()
        
        stats = await db.get_stats()
        consoles = await db.get_consoles()
        
        # Overall stats panel
        status_counts = stats.get('status_counts', {})
        total_games = sum(status_counts.values())
        
        status_text = f"""[bold]Total Games:[/bold] {total_games}
[green]Completed:[/green] {status_counts.get('completed', 0)}
[blue]Downloading:[/blue] {status_counts.get('downloading', 0)}
[yellow]Pending:[/yellow] {status_counts.get('pending', 0)}
[red]Failed:[/red] {status_counts.get('failed', 0)}

[bold]Storage:[/bold]
Total Size: {stats.get('total_size', 0) / (1024**3):.1f} GB
Downloaded: {stats.get('downloaded_bytes', 0) / (1024**3):.1f} GB"""
        
        console.print(Panel(status_text, title="Download Status", border_style="blue"))
        
        # Console breakdown
        if consoles:
            console_table = Table(title="Games by Console")
            console_table.add_column("Console", style="cyan")
            console_table.add_column("Count", style="white")
            
            console_counts = stats.get('console_counts', {})
            for console_name in consoles[:10]:  # Top 10 consoles
                count = console_counts.get(console_name, 0)
                console_table.add_row(console_name, str(count))
            
            console.print(console_table)


@app.command()
def list_games(
    console_filter: Optional[str] = typer.Option(None, "--console", "-c", help="Filter by console"),
    status_filter: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status"),
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum number of results"),
    config_path: Optional[Path] = typer.Option(None, "--config", help="Configuration file path")
):
    """List games in database"""
    asyncio.run(list_games_command(console_filter, status_filter, limit, config_path))


async def list_games_command(
    console_filter: Optional[str], 
    status_filter: Optional[str], 
    limit: int,
    config_path: Optional[Path]
):
    config = load_config(config_path)
    
    status = None
    if status_filter:
        try:
            status = DownloadStatus(status_filter.lower())
        except ValueError:
            console.print(f"[red]Invalid status: {status_filter}[/red]")
            console.print("Valid statuses: pending, downloading, completed, failed")
            return
    
    async with Database(config.database_path) as db:
        await db.init_db()
        
        games = await db.get_game_files(
            status=status,
            console=console_filter,
            limit=limit
        )
        
        if not games:
            console.print("[yellow]No games found matching criteria[/yellow]")
            return
        
        table = Table(title="Games")
        table.add_column("Name", style="white")
        table.add_column("Console", style="green")
        table.add_column("Size", style="yellow")
        table.add_column("Status", style="magenta")
        
        for game in games:
            size_str = f"{game.size_mb:.1f} MB" if game.size else "Unknown"
            status_color = {
                DownloadStatus.COMPLETED: "green",
                DownloadStatus.DOWNLOADING: "blue", 
                DownloadStatus.FAILED: "red",
                DownloadStatus.PENDING: "white"
            }.get(game.status, "white")
            
            table.add_row(
                game.name[:60] + "..." if len(game.name) > 60 else game.name,
                game.console or "Unknown",
                size_str,
                f"[{status_color}]{game.status.value}[/{status_color}]"
            )
        
        console.print(table)


if __name__ == "__main__":
    app()