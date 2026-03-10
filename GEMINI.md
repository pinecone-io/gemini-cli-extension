# Pinecone Extension for Gemini CLI

You have access to the Pinecone MCP server, which provides tools for managing
vector indexes and performing semantic search.

## Available MCP Tools

- `list-indexes` — List all Pinecone indexes
- `describe-index` — Get index configuration and namespaces
- `describe-index-stats` — Get statistics (record counts, namespaces)
- `search-records` — Search with optional metadata filtering and reranking
- `cascading-search` — Search across multiple indexes with deduplication and reranking
- `create-index-for-model` — Create an index with integrated embeddings
- `upsert-records` — Insert or update records
- `rerank-documents` — Rerank using a specialized model
- `search-docs` — Search Pinecone documentation

## Key Concepts

- **Integrated indexes** use Pinecone's hosted embedding models — pass raw text
  and Pinecone handles embedding automatically.
- The `PINECONE_API_KEY` env var must be set. Without it, only doc search works.
- For CLI operations, users may also have `pc` (Pinecone CLI) installed via
  `brew install pinecone-io/tap/pinecone`.

## When to Use Skills

This extension bundles several Agent Skills under `skills/`. Activate them when
the user asks about Pinecone quickstart, querying, CLI usage, assistants, or
needs the MCP tool reference. Prefer activating the relevant skill over
improvising — the skills contain tested, step-by-step workflows.
