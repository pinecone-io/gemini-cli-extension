#!/usr/bin/env python3
# /// script
# dependencies = [
#   "pinecone>=8.0.0",
#   "typer>=0.15.0",
#   "rich>=13.0.0",
# ]
# ///
"""
Chat with a Pinecone Assistant and receive cited responses.

Usage:
    uv run chat.py --assistant NAME --message "Your question" [--stream]

Environment Variables:
    PINECONE_API_KEY: Required Pinecone API key

Output:
    Assistant's response with citations to source documents
"""

import os
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from pinecone import Pinecone
from pinecone_plugins.assistant.models.chat import Message

app = typer.Typer()
console = Console()


@app.command()
def main(
    assistant: str = typer.Option(..., "--assistant", "-a", help="Name of the assistant to chat with"),
    message: str = typer.Option(..., "--message", "-m", help="Your question or message"),
):
    """Chat with a Pinecone Assistant and receive answers with source citations."""

    # Check for API key
    api_key = os.environ.get("PINECONE_API_KEY")
    if not api_key:
        console.print("[red]Error: PINECONE_API_KEY environment variable not set[/red]")
        console.print("\nGet your API key from: https://app.pinecone.io/?sessionType=signup")
        raise typer.Exit(1)

    try:
        # Initialize Pinecone client
        pc = Pinecone(api_key=api_key,source_tag="claude_code_plugin:assistant")
        asst = pc.assistant.Assistant(assistant_name=assistant)

        # Create message
        user_msg = Message(role="user", content=message)

        # Display user question
        console.print(Panel(f"[bold cyan]Question:[/bold cyan] {message}", border_style="cyan"))

        # Get response
        with console.status("[bold blue]Thinking...[/bold blue]"):
            response = asst.chat(messages=[user_msg], stream=False)

        answer_content = response.message.content
        citations = response.citations if hasattr(response, 'citations') else []
        usage = response.usage if hasattr(response, 'usage') else None

        # Display assistant's response (same for both modes)
        console.print("\n[bold green]Answer:[/bold green]\n")

        if answer_content:
            console.print(Panel(answer_content, border_style="green", title="Assistant Response"))
        else:
            console.print("[yellow]No response content received[/yellow]")

        # Display citations if available
        if citations and len(citations) > 0:

            console.print("\n[bold yellow]Citations:[/bold yellow]\n")

            citations_table = Table(show_header=True, header_style="bold yellow")
            citations_table.add_column("#", style="dim", width=4)
            citations_table.add_column("File", style="cyan", width=40)
            citations_table.add_column("Pages", style="blue", width=15)
            citations_table.add_column("Position", style="green", width=10)

            citation_num = 0
            for citation in citations:
                # Each citation has a list of references
                if hasattr(citation, 'references') and citation.references:
                    for reference in citation.references:
                        citation_num += 1

                        # Get file name
                        file_name = "Unknown"
                        if hasattr(reference, 'file') and hasattr(reference.file, 'name'):
                            file_name = reference.file.name

                        # Get pages
                        pages = []
                        if hasattr(reference, 'pages') and reference.pages:
                            pages = reference.pages

                        # Format pages
                        if pages:
                            pages_str = ", ".join(str(p) for p in pages)
                        else:
                            pages_str = "N/A"

                        # Get position from citation
                        position = getattr(citation, 'position', 'N/A')

                        citations_table.add_row(
                            str(citation_num),
                            file_name,
                            pages_str,
                            str(position)
                        )

            console.print(citations_table)

            # Optionally show download links
            console.print("\n[dim]Tip: File URLs are temporary signed links valid for ~1 hour[/dim]")

        # Display token usage
        if usage:
            usage_info = f"""[dim]Tokens used:[/dim]
• Prompt: {getattr(usage, 'prompt_tokens', 'N/A')}
• Completion: {getattr(usage, 'completion_tokens', 'N/A')}
• Total: {getattr(usage, 'total_tokens', 'N/A')}"""
            console.print(Panel(usage_info, border_style="dim", title="Usage Stats"))

        # Follow-up suggestion
        console.print(f"\n[dim]Continue the conversation with another message using the same command[/dim]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
