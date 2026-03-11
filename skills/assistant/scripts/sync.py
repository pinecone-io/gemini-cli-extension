#!/usr/bin/env python3
# /// script
# dependencies = [
#   "pinecone>=8.0.0",
#   "typer>=0.15.0",
#   "rich>=13.0.0",
# ]
# ///
"""
Sync local files to a Pinecone Assistant, only uploading new or changed files.

Usage:
    uv run sync.py --assistant NAME --source PATH [--delete-missing] [--dry-run]

Environment Variables:
    PINECONE_API_KEY: Required Pinecone API key

Output:
    Shows files to add, update, and optionally delete, with confirmation prompt
"""

import os
import hashlib
from pathlib import Path
from datetime import datetime, timezone
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from pinecone import Pinecone

app = typer.Typer()
console = Console()

# Supported file extensions
SUPPORTED_EXTENSIONS = {'.md', '.txt', '.pdf', '.docx', '.json'}

# Directories to exclude
EXCLUDE_DIRS = {'node_modules', '.venv', '.git', 'build', 'dist', '__pycache__', '.pytest_cache'}


def should_exclude_path(path: Path, source_root: Path) -> bool:
    """Check if path should be excluded based on directory patterns."""
    try:
        rel_path = path.relative_to(source_root)
        for part in rel_path.parts:
            if part in EXCLUDE_DIRS or part.startswith('.'):
                return True
    except ValueError:
        return True
    return False


def find_files(source_path: Path) -> list[Path]:
    """Find all supported files in source directory, excluding common build/dependency dirs."""
    files = []

    if source_path.is_file():
        if source_path.suffix.lower() in SUPPORTED_EXTENSIONS:
            return [source_path]
        else:
            return []

    for file_path in source_path.rglob('*'):
        if file_path.is_file():
            if file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
                if not should_exclude_path(file_path, source_path):
                    files.append(file_path)

    return sorted(files)


def get_file_info(file_path: Path):
    """Get file modification time and size."""
    stat = file_path.stat()
    return {
        'mtime': stat.st_mtime,
        'size': stat.st_size,
    }


def file_changed(local_info: dict, remote_metadata: dict) -> bool:
    """Check if local file differs from remote using mtime and size."""
    remote_mtime = remote_metadata.get('mtime')
    remote_size = remote_metadata.get('size')

    if remote_mtime is None or remote_size is None:
        # No stored metadata, assume changed
        return True

    return (local_info['mtime'] != float(remote_mtime) or
            local_info['size'] != int(remote_size))


@app.command()
def main(
    assistant: str = typer.Option(..., "--assistant", "-a", help="Name of the assistant"),
    source: str = typer.Option(..., "--source", "-s", help="Local file or directory path"),
    delete_missing: bool = typer.Option(False, "--delete-missing", help="Delete files from assistant that don't exist locally"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would change without making changes"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """Sync local files to Pinecone Assistant, only uploading new or changed files."""

    # Check for API key
    api_key = os.environ.get("PINECONE_API_KEY")
    if not api_key:
        console.print("[red]Error: PINECONE_API_KEY environment variable not set[/red]")
        console.print("\nGet your API key from: https://app.pinecone.io/?sessionType=signup")
        raise typer.Exit(1)

    # Validate source path
    source_path = Path(source).resolve()
    if not source_path.exists():
        console.print(f"[red]Error: Source path does not exist: {source}[/red]")
        raise typer.Exit(1)

    try:
        # Initialize Pinecone client
        pc = Pinecone(api_key=api_key, source_tag="claude_code_plugin:assistant")
        asst = pc.assistant.Assistant(assistant_name=assistant)

        console.print(Panel(
            f"[bold cyan]Assistant:[/bold cyan] {assistant}\n"
            f"[bold cyan]Source:[/bold cyan] {source_path}",
            title="Sync Configuration",
            border_style="cyan"
        ))

        # Step 1: Get current files in assistant
        with console.status("[bold blue]Fetching assistant files...[/bold blue]", spinner="dots"):
            remote_files = asst.list_files()

        # Build map of file_path -> file object
        remote_file_map = {}
        for f in remote_files:
            metadata = getattr(f, 'metadata', {}) or {}
            file_path = metadata.get('file_path', f.name)
            remote_file_map[file_path] = {
                'file_obj': f,
                'metadata': metadata
            }

        console.print(f"[dim]Found {len(remote_files)} file(s) in assistant[/dim]\n")

        # Step 2: Find local files
        with console.status("[bold blue]Scanning local files...[/bold blue]", spinner="dots"):
            local_files = find_files(source_path)

        if not local_files:
            console.print("[yellow]No supported files found in source path[/yellow]")
            console.print(f"Supported extensions: {', '.join(sorted(SUPPORTED_EXTENSIONS))}")
            raise typer.Exit(0)

        console.print(f"[dim]Found {len(local_files)} local file(s)[/dim]\n")

        # Step 3: Determine what needs syncing
        to_upload = []  # New files
        to_update = []  # Changed files (delete + re-upload)
        to_delete = []  # Files in assistant but not local
        unchanged = []  # Files that match

        # Track which remote files we've seen
        seen_remote_paths = set()

        for local_file in local_files:
            # Get relative path from source root
            if source_path.is_file():
                rel_path = local_file.name
            else:
                rel_path = str(local_file.relative_to(source_path))

            local_info = get_file_info(local_file)

            if rel_path in remote_file_map:
                # File exists remotely, check if changed
                seen_remote_paths.add(rel_path)
                remote_info = remote_file_map[rel_path]

                if file_changed(local_info, remote_info['metadata']):
                    to_update.append({
                        'local_path': local_file,
                        'rel_path': rel_path,
                        'remote_file_id': remote_info['file_obj'].id,
                        'local_info': local_info
                    })
                else:
                    unchanged.append(rel_path)
            else:
                # New file
                to_upload.append({
                    'local_path': local_file,
                    'rel_path': rel_path,
                    'local_info': local_info
                })

        # Find files to delete (in remote but not local)
        if delete_missing:
            for rel_path, remote_info in remote_file_map.items():
                if rel_path not in seen_remote_paths:
                    to_delete.append({
                        'rel_path': rel_path,
                        'remote_file_id': remote_info['file_obj'].id
                    })

        # Step 4: Show summary
        console.print("[bold]Sync Summary:[/bold]\n")

        summary_table = Table(show_header=True, header_style="bold cyan")
        summary_table.add_column("Action", style="yellow", width=15)
        summary_table.add_column("Count", style="green", width=10)

        summary_table.add_row("New files", str(len(to_upload)))
        summary_table.add_row("Updated files", str(len(to_update)))
        if delete_missing:
            summary_table.add_row("Deleted files", str(len(to_delete)))
        summary_table.add_row("Unchanged", str(len(unchanged)))

        console.print(summary_table)
        console.print()

        # Show details if there are changes
        if to_upload:
            console.print("[bold green]Files to upload:[/bold green]")
            for item in to_upload[:10]:  # Show first 10
                console.print(f"  + {item['rel_path']}")
            if len(to_upload) > 10:
                console.print(f"  ... and {len(to_upload) - 10} more")
            console.print()

        if to_update:
            console.print("[bold yellow]Files to update:[/bold yellow]")
            for item in to_update[:10]:
                console.print(f"  ~ {item['rel_path']}")
            if len(to_update) > 10:
                console.print(f"  ... and {len(to_update) - 10} more")
            console.print()

        if to_delete:
            console.print("[bold red]Files to delete:[/bold red]")
            for item in to_delete[:10]:
                console.print(f"  - {item['rel_path']}")
            if len(to_delete) > 10:
                console.print(f"  ... and {len(to_delete) - 10} more")
            console.print()

        # If no changes, exit early
        if not (to_upload or to_update or to_delete):
            console.print("[green]✓ All files are up to date![/green]")
            return

        # Dry run mode
        if dry_run:
            console.print("[yellow]Dry run mode: No changes made[/yellow]")
            return

        # Confirmation prompt
        if not yes:
            proceed = typer.confirm("\nProceed with sync?")
            if not proceed:
                console.print("[yellow]Sync cancelled[/yellow]")
                return

        console.print()

        # Step 5: Execute sync
        uploaded_count = 0
        updated_count = 0
        deleted_count = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:

            # Upload new files
            if to_upload:
                task = progress.add_task(f"Uploading {len(to_upload)} new file(s)...", total=len(to_upload))
                for item in to_upload:
                    try:
                        asst.upload_file(
                            file_path=str(item['local_path']),
                            metadata={
                                'file_path': item['rel_path'],
                                'mtime': item['local_info']['mtime'],
                                'size': item['local_info']['size'],
                                'uploaded_at': datetime.now(timezone.utc).isoformat(),
                                'source': 'sync_script',
                            },
                            timeout=None
                        )
                        uploaded_count += 1
                        progress.advance(task)
                    except Exception as e:
                        console.print(f"[red]Failed to upload {item['rel_path']}: {e}[/red]")

            # Update changed files (delete old + upload new)
            if to_update:
                task = progress.add_task(f"Updating {len(to_update)} file(s)...", total=len(to_update) * 2)
                for item in to_update:
                    try:
                        # Delete old version
                        asst.delete_file(file_id=item['remote_file_id'])
                        progress.advance(task)

                        # Upload new version
                        asst.upload_file(
                            file_path=str(item['local_path']),
                            metadata={
                                'file_path': item['rel_path'],
                                'mtime': item['local_info']['mtime'],
                                'size': item['local_info']['size'],
                                'uploaded_at': datetime.now(timezone.utc).isoformat(),
                                'source': 'sync_script',
                            },
                            timeout=None
                        )
                        updated_count += 1
                        progress.advance(task)
                    except Exception as e:
                        console.print(f"[red]Failed to update {item['rel_path']}: {e}[/red]")

            # Delete missing files
            if to_delete:
                task = progress.add_task(f"Deleting {len(to_delete)} file(s)...", total=len(to_delete))
                for item in to_delete:
                    try:
                        asst.delete_file(file_id=item['remote_file_id'])
                        deleted_count += 1
                        progress.advance(task)
                    except Exception as e:
                        console.print(f"[red]Failed to delete {item['rel_path']}: {e}[/red]")

        # Final summary
        console.print()
        console.print(Panel(
            f"[green]✓ Sync complete![/green]\n\n"
            f"Uploaded: {uploaded_count}\n"
            f"Updated: {updated_count}\n"
            + (f"Deleted: {deleted_count}\n" if delete_missing else "") +
            f"Unchanged: {len(unchanged)}",
            title="Results",
            border_style="green"
        ))

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
