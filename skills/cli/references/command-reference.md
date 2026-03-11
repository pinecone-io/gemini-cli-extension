# Pinecone CLI — Full Command Reference

## Index Management

### Create Index
```bash
# Serverless index
pc index create -n my-index -d 1536 -m cosine -c aws -r us-east-1

# With integrated embedding model
pc index create -n my-index -m cosine -c aws -r us-east-1 \
  --model multilingual-e5-large \
  --field-map text=chunk_text

# Sparse vector index
pc index create -n sparse-index -m dotproduct -c aws -r us-east-1 --vector-type sparse

# With deletion protection
pc index create -n my-index -d 1536 -m cosine -c aws -r us-east-1 --deletion-protection enabled

# From collection
pc index create -n my-index -d 1536 -m cosine -c aws -r us-east-1 --source-collection my-collection
```

### List / Describe / Stats
```bash
pc index list                          # Summary view
pc index list --wide                   # Additional columns (host, embed, tags)
pc index list -j                       # JSON output

pc index describe -n my-index
pc index describe -n my-index -j

pc index stats -n my-index
pc index stats -n my-index --filter '{"genre":{"$eq":"rock"}}'
```

### Configure / Delete
```bash
# Enable deletion protection
pc index configure -n my-index --deletion-protection enabled

# Add tags
pc index configure -n my-index --tags environment=production,team=ml

# Switch to dedicated read capacity
pc index configure -n my-index \
  --read-mode dedicated \
  --read-node-type b1 \
  --read-shards 2 \
  --read-replicas 2

pc index delete -n my-index
```

---

## Vector Operations

### Upsert
```bash
# From JSON file (with "vectors" array)
pc index vector upsert -n my-index --file ./vectors.json

# From JSONL file (one vector per line)
pc index vector upsert -n my-index --file ./vectors.jsonl

# Inline JSON
pc index vector upsert -n my-index --file '{"vectors": [{"id": "vec1", "values": [0.1, 0.2, 0.3]}]}'

# From stdin
cat vectors.json | pc index vector upsert -n my-index --file -

# With namespace, custom batch size
pc index vector upsert -n my-index --namespace tenant-a --file ./vectors.json --batch-size 1000
```

**File formats:**
```json
// JSON (vectors.json)
{"vectors": [{"id": "vec1", "values": [0.1, 0.2, 0.3], "metadata": {"genre": "comedy"}}]}

// JSONL (vectors.jsonl)
{"id": "vec1", "values": [0.1, 0.2, 0.3], "metadata": {"genre": "comedy"}}
{"id": "vec2", "values": [0.4, 0.5, 0.6], "metadata": {"genre": "drama"}}
```

### Query
```bash
# By vector values
pc index vector query -n my-index --vector '[0.1, 0.2, 0.3]' -k 10 --include-metadata

# By vector ID
pc index vector query -n my-index --id "doc-123" -k 10 --include-metadata

# With metadata filter
pc index vector query -n my-index \
  --vector '[0.1, 0.2, 0.3]' \
  --filter '{"genre":{"$eq":"sci-fi"}}' \
  --include-metadata

# Sparse vectors
pc index vector query -n my-index \
  --sparse-indices '[0, 5, 12]' \
  --sparse-values '[0.5, 0.3, 0.8]' \
  -k 15

# From stdin
jq -c '.embedding' doc.json | pc index vector query -n my-index --vector - -k 10
```

### Fetch
```bash
pc index vector fetch -n my-index --ids '["vec1","vec2","vec3"]'
pc index vector fetch -n my-index --filter '{"genre":{"$eq":"rock"}}'
pc index vector fetch -n my-index --namespace tenant-a --ids '["doc-123"]'
pc index vector fetch -n my-index --filter '{"genre":{"$eq":"rock"}}' --limit 100
```

### List / Update / Delete
```bash
# List vector IDs
pc index vector list -n my-index
pc index vector list -n my-index --namespace tenant-a --limit 50

# Update metadata or values
pc index vector update -n my-index --id "vec1" --metadata '{"category":"updated"}'
pc index vector update -n my-index --id "vec1" --values '[0.2, 0.3, 0.4]'

# Bulk update with dry-run
pc index vector update -n my-index \
  --filter '{"genre":{"$eq":"sci-fi"}}' \
  --metadata '{"genre":"fantasy"}' \
  --dry-run

# Delete by IDs or filter
pc index vector delete -n my-index --ids '["vec1","vec2"]'
pc index vector delete -n my-index --filter '{"genre":"classical"}'
pc index vector delete -n my-index --namespace old-data --all-vectors
```

---

## Namespace Management

```bash
pc index namespace create -n my-index --name tenant-a
pc index namespace create -n my-index --name tenant-b --schema "category,brand"
pc index namespace list -n my-index
pc index namespace list -n my-index --prefix "tenant-"
pc index namespace describe -n my-index --name tenant-a
pc index namespace delete -n my-index --name tenant-a   # WARNING: deletes all vectors
```

---

## Backup and Restore

```bash
# Create / list / describe
pc backup create -i my-index -n "nightly-backup" -d "Backup before deployment"
pc backup list
pc backup list --index-name my-index
pc backup describe -i <backup-uuid>

# Restore (creates a new index)
pc backup restore -i <backup-uuid> -n restored-index
pc backup restore -i <backup-uuid> -n restored-index --deletion-protection enabled

# Check restore job status
pc backup restore list
pc backup restore describe -i rj-abc123

# Delete backup
pc backup delete -i <backup-uuid>
```

---

## Project Management

```bash
pc project list
pc project create -n "demo-project"
pc project create -n "demo-project" --target
pc project describe -i proj-abc123
pc project update -i proj-abc123 -n "new-name"
pc project delete -i proj-abc123
```

---

## Organization Management

```bash
pc organization list
pc organization describe -i org-abc123
pc organization update -i org-abc123 -n "new-name"
pc organization delete -i org-abc123   # WARNING: highly destructive
```

---

## API Key Management

```bash
pc api-key create -n "my-key"
pc api-key create -n "my-key" --store
pc api-key create -n "my-key" -i proj-abc123
pc api-key list
pc api-key describe -i key-abc123
pc api-key update -i key-abc123 --roles ProjectEditor
pc api-key delete -i key-abc123
```

---

## Global Flags

Available on all commands:
- `-h, --help` — Show help
- `-j, --json` — JSON output (great for scripting)
- `-q, --quiet` — Suppress output
- `--timeout` — Command timeout (default: 60s, 0 to disable)

## Exit Codes

- `0` — success
- `1` — error

```bash
if pc index describe -n my-index 2>/dev/null; then
  echo "Index exists"
else
  pc index create -n my-index -d 1536 -m cosine -c aws -r us-east-1
fi
```
