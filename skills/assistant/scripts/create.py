#!/usr/bin/env python3
# /// script
# dependencies = [
#   "pinecone>=8.0.0",
#   "typer>=0.15.0",
#   "rich>=13.0.0",
# ]
# ///
"""
Create a new Pinecone Assistant.

Usage:
    uv run create.py --name ASSISTANT_NAME [--instructions TEXT] [--region us|eu] [--timeout SECONDS]

Environment Variables:
    PINECONE_API_KEY: Required Pinecone API key

Output:
    Success message with assistant details including host URL for MCP configuration
"""

import os
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from pinecone import Pinecone

app = typer.Typer()
console = Console()


@app.command()
def main(
    name: str = typer.Option(..., "--name", "-n", help="Unique name for the assistant"),
    instructions: str = typer.Option(
        "",
        "--instructions",
        "-i",
        help="Instructions for assistant behavior (max 16KB)",
    ),
    region: str = typer.Option(
        "us",
        "--region",
        "-r",
        help="Deployment region: 'us' or 'eu'",
    ),
    timeout: int = typer.Option(
        30,
        "--timeout",
        "-t",
        help="Seconds to wait for ready status",
    ),
):
    """Create a new Pinecone Assistant for document Q&A with citations."""

    # Validate region
    if region not in ["us", "eu"]:
        console.print("[red]Error: Region must be 'us' or 'eu'[/red]")
        raise typer.Exit(1)

    # Check for API key
    api_key = os.environ.get("PINECONE_API_KEY")
    if not api_key:
        console.print("[red]Error: PINECONE_API_KEY environment variable not set[/red]")
        console.print("\nGet your API key from: https://app.pinecone.io/?sessionType=signup")
        raise typer.Exit(1)

    try:
        # Initialize Pinecone client
        with console.status(f"[bold blue]Creating assistant '{name}'...[/bold blue]"):
            pc = Pinecone(api_key=api_key, source_tag="claude_code_plugin:assistant")

            # Create assistant
            assistant = pc.assistant.create_assistant(
                assistant_name=name,
                instructions=instructions if instructions else None,
                region=region,
                timeout=timeout,
                metadata={"agentic-ide-source":"claude-code-plugin"}
            )

        # Success message
        console.print(f"\n[bold green]✓ Assistant '{name}' created successfully![/bold green]\n")

        # Display assistant details in a table
        table = Table(show_header=False, box=None)
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Name", assistant.name)
        table.add_row("Region", region)
        table.add_row("Status", f"[yellow]{assistant.status}[/yellow]")
        table.add_row("Host", getattr(assistant, "host", "N/A"))
        if instructions:
            instructions_preview = instructions[:80] + "..." if len(instructions) > 80 else instructions
            table.add_row("Instructions", instructions_preview)

        console.print(table)

        # MCP configuration info
        host = getattr(assistant, "host", "")
        if host:
            mcp_info = f"""[bold]MCP Endpoint:[/bold]
{host}/mcp/assistants/{name}

[bold]Set environment variable:[/bold]
export PINECONE_ASSISTANT_HOST="{host}"
"""
            console.print(Panel(mcp_info, title="MCP Configuration", border_style="blue"))

        # Next steps
        next_steps = f"""[bold]Next steps:[/bold]
1. Upload files: [cyan]/pinecone:assistant-upload assistant {name} source [path][/cyan]
2. Chat: [cyan]/pinecone:assistant-chat assistant {name} message [your question][/cyan]
3. Get context: [cyan]/pinecone:assistant-context assistant {name} query [search][/cyan]"""

        console.print(Panel(next_steps, title="What's Next?", border_style="green"))

    except Exception as e:
        console.print(f"[red]Error creating assistant: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
