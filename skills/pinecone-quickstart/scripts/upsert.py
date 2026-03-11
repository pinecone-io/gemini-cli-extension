#!/usr/bin/env python3
# /// script
# dependencies = [
#   "pinecone>=8.0.0",
#   "typer>=0.15.0",
# ]
# ///

import os
import typer
from pinecone import Pinecone

app = typer.Typer()

@app.command()
def main(
    index: str = typer.Option(..., "--index", help="Name of the Pinecone index to upsert into"),
    namespace: str = typer.Option("example-namespace", "--namespace", help="Namespace to upsert into"),
):
    api_key = os.environ.get("PINECONE_API_KEY")
    if not api_key:
        typer.echo("Error: PINECONE_API_KEY environment variable not set", err=True)
        raise typer.Exit(1)

    pc = Pinecone(api_key=api_key, source_tag="pinecone_skills:upsert")

    records = [
        # Health / feeling unwell
        {"_id": "rec1", "chunk_text": "I've been sneezing all day and my nose won't stop running.", "category": "health"},
        {"_id": "rec2", "chunk_text": "She stayed home with a pounding headache and a low-grade fever.", "category": "health"},
        {"_id": "rec3", "chunk_text": "He felt completely drained after waking up with a sore throat and chills.", "category": "health"},
        # Productivity / work
        {"_id": "rec4", "chunk_text": "She blocked off two hours in the morning to focus without interruptions.", "category": "productivity"},
        {"_id": "rec5", "chunk_text": "He finished all his tasks ahead of schedule by prioritizing the hardest ones first.", "category": "productivity"},
        {"_id": "rec6", "chunk_text": "Turning off notifications helped her get into a deep flow state.", "category": "productivity"},
        # Outdoors / nature
        {"_id": "rec7", "chunk_text": "A red fox darted across the trail and disappeared into the underbrush.", "category": "nature"},
        {"_id": "rec8", "chunk_text": "The hikers paused to watch a bald eagle circle lazily over the valley.", "category": "nature"},
        {"_id": "rec9", "chunk_text": "Fireflies lit up the meadow as the sun dipped below the treeline.", "category": "nature"},
    ]

    idx = pc.Index(index)
    idx.upsert_records(namespace, records)
    typer.echo(f"Upserted {len(records)} records into '{index}' (namespace: '{namespace}')")

if __name__ == "__main__":
    app()
