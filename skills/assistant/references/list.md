# List Assistants

List all Pinecone Assistants in the account with optional file details.

## Arguments

- `--files` (optional flag): Show file details for each assistant
- `--json` (optional flag): JSON output

## Usage

```bash
# Basic listing
uv run scripts/list.py

# With file details
uv run scripts/list.py --files

# JSON output
uv run scripts/list.py --json

# JSON with files (useful for scripting)
uv run scripts/list.py --files --json
```

## Output

**Without `--files`:** Table with name, region, status, host.
**With `--files`:** Adds file count column, plus detailed file tables per assistant showing file name, status, and ID.

File status is color-coded: green = available, yellow = processing.
