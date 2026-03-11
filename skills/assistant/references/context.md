# Retrieve Context Snippets

Get raw context snippets from an assistant's knowledge base without generating a full chat response. Useful for debugging, custom RAG workflows, or quick lookups.

## Arguments

- `--assistant` (required): Assistant name
- `--query` (required): Search query text
- `--top-k` (optional): Number of snippets — default `5`, max `16`
- `--snippet-size` (optional): Max tokens per snippet — default `2048`
- `--json` (optional flag): JSON output

## Workflow

1. Parse arguments. If missing, list assistants and prompt for selection.
2. Execute:
   ```bash
   uv run scripts/context.py \
     --assistant "assistant-name" \
     --query "search text" \
     --top-k 5
   ```
3. Display snippets: file name, page numbers, relevance score, content.

## Context vs Chat

**Use context when:** you want raw snippets, are debugging knowledge, need source material, or are building custom workflows.
**Use chat when:** you want synthesized answers, citations in a conversational response, or multi-turn Q&A.

## Interpreting Results

- **Score:** Higher (closer to 1.0) = more relevant
- **Low scores (<0.5):** Weak match, assistant may need more relevant documents, or query is too broad/specific

## Troubleshooting

**No results** — try broader search terms; suggest uploading more documents.
**context method not available** — update SDK: `pip install --upgrade pinecone` (requires v8.0.0+).
**Assistant not found** — check name for typos, run list command.
