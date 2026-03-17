# Pinecone Extension for Gemini CLI

You have access to the Pinecone MCP server and a suite of specialized Agent Skills for managing vector indexes, performing semantic search, and building document Q&A assistants.

## Available Agent Skills

This extension bundles several Agent Skills under `skills/`. Gemini CLI is configured to auto-invoke these skills based on your intent. If you experience routing issues, you can explicitly request a skill by name (e.g., "Use the quickstart skill").

| Skill | Description |
|---|---|
| `quickstart` | Interactive onboarding for new developers. Choose between Database (vector search) or Assistant (document Q&A) paths. |
| `query` | Search integrated indexes (those with built-in embedding models) using natural language text via the Pinecone MCP. |
| `cli` | Guide for using the Pinecone CLI (`pc`) for terminal-based management of all index types and advanced vector operations. |
| `assistant` | Create, manage, and chat with Pinecone Assistants for document Q&A with citations. |
| `mcp` | Reference for all available Pinecone MCP server tools and their parameters. |
| `pinecone-docs` | Curated links to official Pinecone documentation, organized by topic. |
| `help` | Overview of all available Pinecone skills and setup requirements. |

## Key Concepts & Setup

- **Integrated Indexes:** These use Pinecone's hosted embedding models. You can pass raw text, and Pinecone handles embedding automatically.
- **PINECONE_API_KEY:**
    - **Required for MCP:** Must be configured in your Gemini CLI / MCP settings.
    - **Required for Skills:** Many skills run bundled Python scripts. You **must** also export the key in your terminal (`export PINECONE_API_KEY="your-key"`) for these scripts to function.
- **Tools:** Use the `cli` skill if you need to manage standard (non-integrated) indexes or perform bulk vector operations that the MCP does not yet support.

## Available MCP Tools

- `list-indexes` — List all Pinecone indexes.
- `describe-index` — Get index configuration and namespaces.
- `describe-index-stats` — Get statistics (record counts, namespaces).
- `search-records` — Search with optional metadata filtering and reranking.
- `cascading-search` — Search across multiple indexes with deduplication and reranking.
- `create-index-for-model` — Create an index with integrated embeddings.
- `upsert-records` — Insert or update records.
- `rerank-documents` — Rerank using a specialized model.
- `search-docs` — Search Pinecone documentation.

For detailed usage of any MCP tool, invoke the `mcp` skill.
