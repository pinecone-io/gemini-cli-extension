# Data Formats

## Integrated Index Records

Used with `upsert_records()` (Python SDK) or `upsert-records` (MCP). Records are automatically embedded using the index's configured model.

**JSON**
```json
[
  {
    "_id": "rec1",
    "chunk_text": "Your text content here.",
    "category": "example"
  },
  {
    "_id": "rec2",
    "chunk_text": "Another piece of text.",
    "category": "example"
  }
]
```

- `_id` — unique record identifier (required)
- The text field name must match the index's `fieldMap` (e.g. `chunk_text` if `fieldMap: {text: "chunk_text"}`)
- All other fields are stored as metadata and can be used for filtering
- Do **not** nest extra fields under a `metadata` key — put them directly on the record

---

## Standard Index Vectors

Used with `upsert()` (Python SDK) or `pc index vector upsert` (CLI).

**JSON (with `vectors` array)**
```json
{
  "vectors": [
    {
      "id": "vec1",
      "values": [0.1, 0.2, 0.3],
      "metadata": { "genre": "comedy", "year": 2021 }
    },
    {
      "id": "vec2",
      "values": [0.4, 0.5, 0.6],
      "metadata": { "genre": "drama", "year": 2019 }
    }
  ]
}
```

**JSONL (one vector per line)**
```jsonl
{"id": "vec1", "values": [0.1, 0.2, 0.3], "metadata": {"genre": "comedy"}}
{"id": "vec2", "values": [0.4, 0.5, 0.6], "metadata": {"genre": "drama"}}
```

- `id` — unique vector identifier (required)
- `values` — dense vector as float array, length must match index dimension (required)
- `metadata` — arbitrary key-value pairs for filtering (optional)

---

## Sparse Vectors

Used for keyword or hybrid search with sparse indexes.

```json
{
  "id": "vec1",
  "values": [0.1, 0.2, 0.3],
  "sparse_values": {
    "indices": [10, 45, 316],
    "values": [0.5, 0.3, 0.8]
  },
  "metadata": { "genre": "comedy" }
}
```

- `sparse_values.indices` — non-zero dimension indices
- `sparse_values.values` — corresponding float values, same length as `indices`
