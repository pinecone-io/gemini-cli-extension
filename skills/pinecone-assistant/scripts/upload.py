#!/usr/bin/env python3
# /// script
# dependencies = [
#   "pinecone>=8.0.0",
#   "typer>=0.15.0",
#   "rich>=13.0.0",
# ]
# ///
"""
Upload files or repository contents to a Pinecone Assistant.

IMPORTANT: Only uploads DOCUMENTATION and DATA files.
Supported: DOCX (.docx), JSON (.json), Markdown (.md), PDF (.pdf), Text (.txt)
Code files are NOT supported by Pinecone Assistant.

Usage:
    uv run upload.py --assistant NAME --source PATH [--patterns "*.md,*.pdf,*.docx"]

Environment Variables:
    PINECONE_API_KEY: Required Pinecone API key

Output:
    Progress updates and summary of uploaded files
"""

import os
import glob
from pathlib import Path
from typing import List
from datetime import datetime, timezone
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.panel import Panel
from pinecone import Pinecone

app = typer.Typer()
console = Console()

# Default file patterns - DOCUMENTATION ONLY
# Assistant supports: DOCX, JSON, Markdown, PDF, Text
DEFAULT_PATTERNS = ["**/*.md", "**/*.txt", "**/*.pdf", "**/*.docx", "**/*.json"]

# Default directories to exclude
DEFAULT_EXCLUDES = ["node_modules", ".venv", "venv", ".git", "build", "dist", "__pycache__", ".next", ".cache"]


def find_files(source_path: str, patterns: List[str], excludes: List[str]) -> List[Path]:
    """Find files matching patterns, excluding certain directories."""
    source = Path(source_path)

    if not source.exists():
        console.print(f"[red]Error: Path '{source_path}' does not exist[/red]")
        raise typer.Exit(1)

    # If it's a single file, return it
    if source.is_file():
        return [source]

    # Otherwise, scan directory
    files = []
    for pattern in patterns:
        matched = glob.glob(str(source / pattern), recursive=True)
        files.extend([Path(f) for f in matched])

    # Filter out excluded directories
    filtered_files = []
    for file_path in files:
        # Check if any exclude pattern is in the path
        if not any(excl in str(file_path) for excl in excludes):
            filtered_files.append(file_path)

    return sorted(set(filtered_files))


@app.command()
def main(
    assistant: str = typer.Option(..., "--assistant", "-a", help="Name of the assistant to upload to"),
    source: str = typer.Option(..., "--source", "-s", help="File or directory path to upload"),
    patterns: str = typer.Option(
        ",".join(DEFAULT_PATTERNS),
        "--patterns",
        "-p",
        help="Comma-separated glob patterns for documentation files (e.g., '*.md,*.pdf')",
    ),
    exclude: str = typer.Option(
        ",".join(DEFAULT_EXCLUDES),
        "--exclude",
        "-e",
        help="Comma-separated directories to exclude",
    ),
    metadata_json: str = typer.Option(
        "",
        "--metadata",
        "-m",
        help="Additional metadata as JSON string",
    ),
):
    """Upload documentation files to a Pinecone Assistant.

    NOTE: Only documentation files (markdown, text, PDF) are supported.
    Code files are not recommended for Pinecone Assistant.
    """

    # Check for API key
    api_key = os.environ.get("PINECONE_API_KEY")
    if not api_key:
        console.print("[red]Error: PINECONE_API_KEY environment variable not set[/red]")
        console.print("\nGet your API key from: https://app.pinecone.io/?sessionType=signup")
        raise typer.Exit(1)

    # Parse patterns and excludes
    pattern_list = [p.strip() for p in patterns.split(",")]
    exclude_list = [e.strip() for e in exclude.split(",")]

    # Parse additional metadata if provided
    extra_metadata = {}
    if metadata_json:
        import json
        try:
            extra_metadata = json.loads(metadata_json)
        except json.JSONDecodeError:
            console.print("[red]Error: Invalid JSON in --metadata parameter[/red]")
            raise typer.Exit(1)

    try:
        # Initialize Pinecone client
        pc = Pinecone(api_key=api_key, source_tag="claude_code_plugin:assistant")
        asst = pc.assistant.Assistant(assistant_name=assistant)

        # Find files to upload
        console.print(f"\n[bold]Scanning for documentation files in:[/bold] {source}")
        console.print(f"[dim]Patterns: {', '.join(pattern_list)}[/dim]\n")

        files = find_files(source, pattern_list, exclude_list)

        if not files:
            console.print("[yellow]No documentation files found matching the specified patterns[/yellow]")
            console.print("\n[dim]Tip: Pinecone Assistant works with .md, .txt, and .pdf files[/dim]")
            return

        console.print(f"[green]Found {len(files)} documentation file(s) to upload[/green]\n")

        # Upload files with progress bar
        uploaded = 0
        failed = 0
        failed_files = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]Uploading files...", total=len(files))

            for file_path in files:
                try:
                    # Build metadata
                    rel_path = os.path.relpath(str(file_path), source)
                    stat = file_path.stat()
                    metadata = {
                        "source": "upload_script",
                        "file_path": rel_path,
                        "file_type": file_path.suffix,
                        "content_type": "documentation",
                        "mtime": stat.st_mtime,
                        "size": stat.st_size,
                        "uploaded_at": datetime.now(timezone.utc).isoformat(),
                        **extra_metadata,
                    }

                    # Upload file
                    asst.upload_file(
                        file_path=str(file_path),
                        metadata=metadata,
                        timeout=None,
                    )
                    uploaded += 1
                    progress.update(task, advance=1, description=f"[cyan]Uploaded: {rel_path}")

                except Exception as e:
                    failed += 1
                    failed_files.append((str(file_path), str(e)))
                    progress.update(task, advance=1)

        # Summary table
        console.print()
        summary = Table(show_header=False, box=None)
        summary.add_column("Status", style="bold")
        summary.add_column("Count")

        summary.add_row("[green]✓ Uploaded[/green]", str(uploaded))
        if failed > 0:
            summary.add_row("[red]✗ Failed[/red]", str(failed))

        console.print(Panel(summary, title="Upload Summary", border_style="blue"))

        # Show failed files if any
        if failed_files:
            console.print("\n[bold red]Failed uploads:[/bold red]")
            for file_path, error in failed_files:
                console.print(f"  • {file_path}: [red]{error}[/red]")

        # Next steps
        if uploaded > 0:
            next_steps = f"""[bold]Next steps:[/bold]
• Chat: [cyan]/pinecone:assistant-chat assistant {assistant} message [your question][/cyan]
• Context: [cyan]/pinecone:assistant-context assistant {assistant} query [search][/cyan]

[dim]Note: Files are being processed and will be available shortly[/dim]"""
            console.print(Panel(next_steps, title="What's Next?", border_style="green"))

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
