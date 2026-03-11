# Chat with Assistant

Send a message to an assistant and receive a cited response.

## Arguments

- `--assistant` (required): Assistant name
- `--message` (required): The question or message
- `--stream` (optional flag): Enable streaming for faster perceived response

## Workflow

1. Parse arguments. If assistant missing, run `uv run scripts/list.py --json` and ask the user to select.
2. If message missing, prompt user for their question.
3. Execute:
   ```bash
   uv run scripts/chat.py \
     --assistant "assistant-name" \
     --message "user's question"
   ```
4. Display:
   - Assistant's response
   - Citations table: citation number, source file, page numbers, position
   - Token usage statistics

**Note:** File URLs in citations are temporary signed links (~1 hour). They are not displayed in output.

## Troubleshooting

**Assistant not found** — run list command, check for typos.
**No response or timeout** — verify assistant has files uploaded and status is "ready" (not "indexing").
**Empty or poor responses** — assistant may lack relevant documents; suggest upload.
**PINECONE_API_KEY not set** — export the variable or add to a `.env` file, then restart your IDE/agent session.
