# Pinecone CLI — Troubleshooting & Best Practices

## Troubleshooting

### Authentication Issues

**"Not authenticated" or "Invalid credentials"**
```bash
pc auth status
pc logout
pc login
pc target -o "my-org" -p "my-project"
```

**Service account can't access resources**
```bash
pc target --show   # Verify correct project is targeted
```

### API Key Issues

**API key not working**
```bash
pc config get-api-key   # Verify key is set
# API keys are scoped to org + project — get a new one if needed
pc api-key create -n "new-key" --store
```

### Target Context Issues

**"Project not found" or "Organization not found"**
```bash
pc target --show
pc target --clear
pc target -o "my-org" -p "my-project"
```

### Index Issues

**Index operations failing**
```bash
pc index describe -n my-index
# "Initializing" → wait and retry
# "Terminating" → recreate it
```

**Can't delete index**
```bash
# Check if deletion protection is on
pc index describe -n my-index
pc index configure -n my-index --deletion-protection disabled
pc index delete -n my-index
```

### Vector Upload Issues

**Upsert fails with dimension mismatch**
```bash
pc index describe -n my-index   # Check configured dimension
# Ensure all vectors have exactly that many values
```

**Large file upload is slow**
```bash
# Use max batch size
pc index vector upsert -n my-index --file ./large.json --batch-size 1000

# Or split JSONL and loop
split -l 10000 large.jsonl chunk-
for file in chunk-*; do
  pc index vector upsert -n my-index --file "$file"
done
```

### Query Issues

**Query returns no results**
```bash
pc index stats -n my-index          # Check if data exists
pc index namespace list -n my-index # Verify namespace
# Filters use MongoDB query syntax — double-check filter format
```

### Backup Issues

**Backup creation fails**
```bash
pc index describe -n my-index
# Backups are only supported for serverless indexes in "Ready" state
```

**Can't find backup ID**
```bash
pc backup list --index-name my-index
# Use the UUID (e.g. c84725e5-...) not the name for restore/delete
```

---

## Best Practices

### Use the right auth method
- **Interactive dev**: `pc login`
- **CI/CD pipelines**: service accounts
- **Quick testing**: `pc api-key create -n "my-key" --store`

### Check status before operating
```bash
pc auth status
pc target --show
pc index describe -n my-index
```

### Use JSON output for scripts
```bash
pc index list -j | jq -r '.[] | .name'
```

### Preview destructive operations
```bash
pc index vector update -n my-index \
  --filter '{"genre":{"$eq":"old"}}' \
  --metadata '{"genre":"new"}' \
  --dry-run
```

### Protect production indexes
```bash
pc index create -n prod-index -d 1536 -m cosine -c aws -r us-east-1 \
  --deletion-protection enabled
```

### Automate backups
```bash
pc backup create -i my-index -n "daily-backup-$(date +%Y%m%d)"
```
