# Sync Files

Incrementally sync local files to an assistant — only uploads new or changed files. Uses mtime and size to detect changes.

## Arguments

- `--assistant` (required): Assistant name
- `--source` (required): Local file or directory path
- `--delete-missing` (optional flag): Delete files from assistant that no longer exist locally
- `--dry-run` (optional flag): Preview changes without executing
- `--yes` / `-y` (optional flag): Skip confirmation prompt

## Workflow

1. Parse arguments. If missing, list assistants and prompt for selection.
2. Execute:
   ```bash
   uv run scripts/sync.py \
     --assistant "assistant-name" \
     --source "./docs" \
     [--delete-missing] \
     [--dry-run] \
     [--yes]
   ```
3. Script compares local files against stored metadata, shows summary, asks for confirmation (unless `--yes`).

## Flags

- **`--delete-missing`** — removes files from the assistant that no longer exist locally. Use when cleaning up removed content.
- **`--dry-run`** — shows exactly what would change with no side effects. Always recommend this first.
- **`--yes`** — skips confirmation. Useful for automation; combine with `--dry-run` to verify first.

## Common Workflow

```bash
# Preview first
uv run scripts/sync.py --assistant my-docs --source ./docs --dry-run

# Then apply
uv run scripts/sync.py --assistant my-docs --source ./docs

# Keep in sync after git pull
git pull
uv run scripts/sync.py --assistant my-docs --source ./docs --delete-missing
```

## Troubleshooting

**Files showing as changed but content unchanged** — mtime updates on save even without content changes; harmless, file will be re-uploaded.
**Sync is slow** — each update = delete + re-upload (2 operations); use `--dry-run` first to check scope.
**No supported files found** — check source contains `.md`, `.txt`, `.pdf`, `.docx`, or `.json` files not in excluded directories.
