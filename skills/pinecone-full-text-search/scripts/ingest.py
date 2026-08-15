#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
#   "pinecone==9.0.0",
# ]
# ///
"""Ingest a JSONL file into a Pinecone FTS index — safely.

A bare-LLM ingest path skips three things and breaks in three different ways:

  1. Per-doc upsert in a Python loop instead of `batch_upsert`. Slow.
  2. Discards the upsert response. Silent failures look like success.
  3. Doesn't poll. The HTTP call returns 202 before async indexing finishes,
     so the next search call comes back empty and looks like a query bug.

This script does all three correctly:

  1. Bulk-upserts in batches.
  2. Inspects every batch result; aborts loudly on any error.
  3. Polls `documents.search` with a sentinel query until matches appear.

You provide prepared, schema-conformant JSONL + the index name. Schema
validation belongs upstream;
this script trusts the input and focuses on getting it indexed safely.

Usage:

    uv run --script ingest.py \\
      --data processed.jsonl \\
      --index articles \\
      --sentinel-field body

Run `--help` for the full flag list.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import typer
from pinecone import Pinecone


# ---------------------------------------------------------------------------
# Helpers — small functions, each does one thing.
# ---------------------------------------------------------------------------

def load_jsonl(path: Path) -> list[dict]:
    """Read a JSONL file into a list of dicts. Fail loudly on parse errors."""
    docs: list[dict] = []
    for lineno, line in enumerate(path.read_text().splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            docs.append(json.loads(line))
        except json.JSONDecodeError as e:
            raise typer.BadParameter(f"{path}:{lineno}: invalid JSON ({e.msg})")
    if not docs:
        raise typer.BadParameter(f"{path}: file is empty")
    return docs


def pick_sentinel_token(docs: list[dict], field: str) -> str:
    """Pick a token from `docs[*][field]` to use as the readiness-poll query.

    A sentinel just needs to match *something* in the freshly-ingested data.
    Scan from the first doc onward and return the first whitespace-split token
    we find — first-doc-is-special datasets (cover pages, header rows, test
    records with empty bodies) won't make us abort.
    """
    for doc in docs:
        val = doc.get(field)
        if isinstance(val, str) and val.strip():
            return val.strip().split()[0]
    sample = ", ".join(sorted(docs[0].keys())) or "(none)"
    raise typer.BadParameter(
        f"can't auto-pick sentinel: no document has a non-empty string in {field!r} "
        f"(scanned all {len(docs)} record(s)). Available fields in doc[0]: {sample}. "
        f"Either fix --sentinel-field, or pass --sentinel TEXT explicitly."
    )


def upsert_batches(
    idx,
    namespace: str,
    docs: list[dict],
    batch_size: int,
) -> int:
    """Bulk-upsert in batches; abort on the first failed batch.

    Why we inspect the result every time:
        `batch_upsert` returns 202 even when individual documents fail — the
        failures are reported in `result.errors` / `result.has_errors`.
    """
    upserted = 0
    for start in range(0, len(docs), batch_size):
        batch = docs[start:start + batch_size]
        t0 = time.time()
        result = idx.documents.batch_upsert(namespace=namespace, documents=batch)
        elapsed = time.time() - t0

        has_errors = getattr(result, "has_errors", False) or getattr(result, "failed_batch_count", 0)
        if has_errors:
            for err in getattr(result, "errors", []) or []:
                msg = getattr(err, "error_message", None) or str(err)
                typer.secho(f"  batch error: {msg}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)

        upserted += len(batch)
        typer.echo(
            f"  batch @{start:>6}: {len(batch):>4} docs in {elapsed:>5.2f}s"
            f"  (total: {upserted}/{len(docs)})"
        )
    return upserted


def poll_until_searchable(
    idx,
    namespace: str,
    sentinel_field: str,
    sentinel_token: str,
    deadline_s: int,
) -> tuple[float, int]:
    """Poll `documents.search` until the sentinel query returns matches.

    Why this exists:
        After `batch_upsert` returns, Pinecone is still building the inverted
        index. A search call that arrives during that window comes back empty.
        Without this poll, the user sees an empty `documents.search` and
        debugs their *query*, never noticing it was an indexing race.

    Returns:
        (seconds_elapsed, number_of_probes)
    """
    start = time.time()
    deadline = start + deadline_s
    probes = 0
    while time.time() < deadline:
        probes += 1
        resp = idx.documents.search(
            namespace=namespace,
            top_k=1,
            score_by=[{"type": "text", "field": sentinel_field, "query": sentinel_token}],
            include_fields=[],  # required on every search; [] = lightest payload
        )
        if resp.matches:
            return time.time() - start, probes
        time.sleep(5)

    raise typer.Exit(code=1)


def resolve_index_with_retry(pc, name: str, *, deadline_s: int = 60):
    """Resolve `pc.preview.index(name=...)`, retrying briefly during data-plane warmup.

    """
    deadline = time.time() + deadline_s
    delay = 2.0
    last_exc = None
    while time.time() < deadline:
        try:
            return pc.preview.index(name=name)
        except Exception as exc:
            last_exc = exc
            time.sleep(delay)
            delay = min(delay * 1.5, 8.0)
    raise typer.Exit(
        f"Could not resolve index '{name}' within {deadline_s}s "
        f"(last error: {type(last_exc).__name__}: {last_exc}). "
        f"Check the index exists, the API key has access to it, and that the "
        f"data-plane host has finished provisioning (control-plane `status.ready: True` "
        f"can lag the data plane by a few seconds)."
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

app = typer.Typer(
    add_completion=False,
    help="Ingest a JSONL file into a Pinecone FTS index, safely.",
    rich_markup_mode="rich",
)


@app.command()
def main(
    data: Path = typer.Option(
        ..., "--data", "-d",
        exists=True, dir_okay=False, readable=True,
        help="Path to JSONL of prepared, schema-conformant documents (one per line).",
    ),
    index: str = typer.Option(
        ..., "--index", "-i",
        help="Pinecone index name.",
    ),
    sentinel_field: str = typer.Option(
        ..., "--sentinel-field", "-f",
        help="An FTS-enabled field on the index. Used for the readiness-poll query. "
             "If you don't know which to use, pick the longest free-text field on your schema.",
    ),
    namespace: str = typer.Option(
        "__default__", "--namespace", "-n",
        help="Index namespace.",
    ),
    batch_size: int = typer.Option(
        100, "--batch-size", "-b", min=1, max=200,
        help="Documents per batch_upsert call. Reduce if your dense vectors are large "
             "(e.g. 50 for dim=3072) and you hit payload-size errors.",
    ),
    poll_deadline: int = typer.Option(
        300, "--poll-deadline", min=10, max=3600,
        help="Seconds to wait for docs to become searchable before giving up.",
    ),
    sentinel: str | None = typer.Option(
        None, "--sentinel", "-s",
        help="Token used for the readiness-poll query. "
             "Default: first word of doc[0][sentinel-field].",
    ),
):
    """Bulk-ingest prepared documents into a Pinecone FTS index.

    [bold]Pipeline[/bold]

      1. Load JSONL.
      2. `batch_upsert` in batches; abort on any batch error.
      3. Poll `documents.search` with a sentinel query until matches appear.
      4. Report timings.

    [bold]Required[/bold]: PINECONE_API_KEY in the environment, an existing
    index named [bold]--index[/bold], and prepared JSONL at [bold]--data[/bold].
    """
    if not os.environ.get("PINECONE_API_KEY"):
        raise typer.Exit("PINECONE_API_KEY not set in environment.")

    typer.echo(f"Loading {data} ...")
    docs = load_jsonl(data)
    typer.echo(f"Loaded {len(docs)} document(s).")

    if sentinel is None:
        sentinel = pick_sentinel_token(docs, sentinel_field)
    typer.echo(f"Sentinel: {sentinel_field}={sentinel!r}")

    pc = Pinecone(source_tag="pinecone_skills:full_text_search_ingest")  # reads PINECONE_API_KEY
    idx = resolve_index_with_retry(pc, index)

    typer.echo(f"\nUpserting in batches of {batch_size} ...")
    t_upsert_start = time.time()
    upserted = upsert_batches(idx, namespace, docs, batch_size)
    upsert_seconds = time.time() - t_upsert_start
    typer.echo(f"\nUpsert complete: {upserted} doc(s) in {upsert_seconds:.1f}s.")

    typer.echo(f"\nPolling for searchability (deadline {poll_deadline}s) ...")
    try:
        poll_seconds, probes = poll_until_searchable(
            idx, namespace, sentinel_field, sentinel, poll_deadline,
        )
    except typer.Exit:
        typer.secho(
            f"\nDocs not searchable within {poll_deadline}s. "
            f"Sentinel: {sentinel_field}={sentinel!r}. "
            f"Possible causes: sentinel field isn't FTS-enabled on this index; "
            f"the upserts succeeded structurally but the documents themselves were "
            f"rejected by the inverted-index builder; the deadline is too tight.",
            fg=typer.colors.RED, err=True,
        )
        raise

    typer.echo(f"Searchable after {poll_seconds:.1f}s ({probes} probe(s)).")
    typer.echo(f"\nDone — total {upsert_seconds + poll_seconds:.1f}s.")


if __name__ == "__main__":
    app()