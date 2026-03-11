#!/usr/bin/env python3
# /// script
# dependencies = [
#   "pinecone>=8.0.0",
#   "typer>=0.15.0",
#   "rich>=13.0.0",
# ]
# ///
"""
Retrieve context snippets from a Pinecone Assistant's knowledge base.

Usage:
    uv run context.py --assistant NAME --query "search text" [--top-k 5] [--json]

Environment Variables:
    PINECONE_API_KEY: Required Pinecone API key

Output:
    Relevant context snippets with file sources, page numbers, and relevance scores
"""

import os
import json as json_module
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from pinecone import Pinecone

app = typer.Typer()
console = Console()


@app.command()
def main(
    assistant: str = typer.Option(..., "--assistant", "-a", help="Name of the assistant"),
    query: str = typer.Option(..., "--query", "-q", help="Search query text"),
    top_k: int = typer.Option(5, "--top-k", "-k", help="Number of results to return (max 16)"),
    snippet_size: int = typer.Option(1024, "--snippet-size", "-s", help="Maximum tokens per snippet"),
    json: bool = typer.Option(False, "--json", help="Output in JSON format"),
):
    """Retrieve relevant context snippets from an assistant's knowledge base."""

    # Check for API key
    api_key = os.environ.get("PINECONE_API_KEY")
    if not api_key:
        console.print("[red]Error: PINECONE_API_KEY environment variable not set[/red]")
        console.print("\nGet your API key from: https://app.pinecone.io/?sessionType=signup")
        raise typer.Exit(1)

    try:
        # Initialize Pinecone client
        pc = Pinecone(api_key=api_key, source_tag="claude_code_plugin:assistant")
        asst = pc.assistant.Assistant(assistant_name=assistant)

        # Display query
        if not json:
            console.print(Panel(f"[bold cyan]Query:[/bold cyan] {query}", border_style="cyan"))

        # Retrieve context
        with console.status("[bold blue]Searching knowledge base...[/bold blue]", spinner="dots"):
            response = asst.context(query=query, top_k=top_k, snippet_size=snippet_size)

        # Get snippets from response
        snippets = response.snippets if hasattr(response, 'snippets') else []

        if json:
            # JSON output
            results = []
            for snippet in snippets:
                file_name = "Unknown"
                pages = []
                if hasattr(snippet, 'reference') and snippet.reference:
                    ref = snippet.reference
                    if hasattr(ref, 'file') and hasattr(ref.file, 'name'):
                        file_name = ref.file.name
                    if hasattr(ref, 'pages') and ref.pages:
                        pages = ref.pages

                results.append({
                    "file_name": file_name,
                    "pages": pages,
                    "content": getattr(snippet, 'content', ''),
                    "score": getattr(snippet, 'score', 0.0),
                    "type": getattr(snippet, 'type', 'text'),
                })
            print(json_module.dumps({"snippets": results, "count": len(results)}, indent=2))
        else:
            # Rich formatted output
            if not snippets or len(snippets) == 0:
                console.print("[yellow]No context found for this query[/yellow]")
                return

            console.print(f"\n[bold]Found {len(snippets)} relevant snippet(s):[/bold]\n")

            for idx, snippet in enumerate(snippets, 1):
                # Extract file info from reference
                file_name = "Unknown"
                pages = []
                if hasattr(snippet, 'reference') and snippet.reference:
                    ref = snippet.reference
                    if hasattr(ref, 'file') and hasattr(ref.file, 'name'):
                        file_name = ref.file.name
                    if hasattr(ref, 'pages') and ref.pages:
                        pages = ref.pages

                score = getattr(snippet, 'score', 0.0)
                content = getattr(snippet, 'content', '')

                # Create header
                header = f"#{idx} - {file_name}"
                if pages:
                    pages_str = ", ".join(str(p) for p in pages)
                    header += f" (Page {pages_str})"
                header += f" - Score: {score:.3f}" if isinstance(score, (int, float)) else f" - Score: {score}"

                console.print(Panel(
                    content,
                    title=header,
                    border_style="blue",
                    subtitle=f"[dim]Relevance: {score:.2%}[/dim]" if isinstance(score, (int, float)) else None
                ))
                console.print()

            # Suggest next action
            next_action = f"""[bold]Next steps:[/bold]
• Ask a question: [cyan]/pinecone:assistant-chat assistant {assistant} message [your question][/cyan]
• Upload more files: [cyan]/pinecone:assistant-upload assistant {assistant} source [path][/cyan]"""
            console.print(Panel(next_action, title="What's Next?", border_style="green"))

    except AttributeError as e:
        # Handle case where context method doesn't exist or response structure is different
        console.print(f"[red]Error: Context retrieval failed[/red]")
        console.print(f"[dim]Details: {e}[/dim]")
        console.print("\n[yellow]Note:[/yellow] Context API requires SDK version with assistant.context() support")
        console.print("\n[yellow]Try using chat instead:[/yellow]")
        console.print(f"  /pinecone:assistant-chat assistant {assistant} message \"{query}\"")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
