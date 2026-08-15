# Ingestion

Writing documents into a Pinecone preview document index uses two methods. Pick based on volume, then handle the *async indexing* gotcha on the other side.

## `documents.upsert` — small writes / patches

```python
idx = pc.preview.index(name=INDEX_NAME)

upsert_resp = idx.documents.upsert(
    namespace=NAMESPACE,
    documents=[
        {
            "_id": "doc-1",
            "title": "A landmark work that every reader should experience.",
            "body": "Lorem ipsum...",
            "category": "fiction",
            "year": 2024.0,
        },
        # ... up to ~1000 documents per call (per public-preview docs)
    ],
)
print(upsert_resp.upserted_count)
```

Use `upsert` when:

- You're writing a single document (e.g. a sentinel doc to verify end-to-end before a bulk load).
- You're "patching" a doc after a correction. *Note*: `2026-01.alpha` has **no per-field merge** — every upsert replaces the entire document on conflicting `_id`. To update a single field, fetch the doc, modify in client code, and upsert the full doc back under the same `_id`.
- You're streaming writes from user actions and each request fits in a single batch.

Each document is a dict keyed by field name. `_id` is required and must be a non-empty unique string within the namespace. Values must match the declared schema types (FTS strings → `str`, filterable `float` → `int|float`, dense vectors → `list[float]`, sparse → `{"indices": [...], "values": [...]}`). Field names that start with `_` or `$` are rejected; field names are limited to 64 bytes.

The endpoint returns `202 Accepted` (async) and the body's `upserted_count` is the number of items accepted, not the number that have finished indexing.

## `documents.batch_upsert` — bulk loads

```python
result = idx.documents.batch_upsert(
    namespace=NAMESPACE,
    documents=documents,        # list of dicts, any length
    batch_size=50,
    max_workers=2,
    show_progress=True,
)
print(f"{result.successful_item_count:,} / {result.total_item_count:,} succeeded")
if result.has_errors:
    print(f"Failed batches: {result.failed_batch_count}")
    # Always surface the actual reason — silent failures mask payload-size
    # caps, schema mismatches, and reserved-field-name violations.
    for err in result.errors[:3]:
        sample = err.items[0].get("_id") if err.items else "?"
        print(f"  batch #{err.batch_index} ({len(err.items)} items, "
              f"first _id={sample!r}): {err.error_message}")
```

The SDK splits `documents` into `batch_size`-sized chunks and uploads them over `max_workers` parallel HTTP connections. `show_progress=True` prints a tqdm-style bar.

### Tuning `batch_size` and `max_workers`

- **`batch_size=50`** is the sweet spot — comfortably below the per-request cap and small enough that transient failures cost less to redo.
- **`max_workers=2`** is a safe default. Bump to `4` for large (thousands-of-docs) loads where you're not simultaneously embedding. Ramp cautiously above 4 — you'll hit Pinecone or upstream embedding-provider rate limits first.
- If you're embedding on the fly (computing vectors inside the upsert loop), keep `max_workers` low so embedding latency dominates rather than index write latency.

### Document and request size caps

**Hard limits in `2026-01.alpha`:**

- **Per document**: max **2 MB** (serialized JSON, all stored fields combined).
- **Per `full_text_search` string field**: max **100 KB** AND max **10,000 tokens**. Tokens longer than 256 bytes are silently truncated by the analyzer.
- **Per upsert request**: max **2 MB total** AND max **1,000 documents**.
- **Per document filterable metadata** (everything *not* in an FTS field): max **40 KB** combined.
- **Schema-level**: up to **100 FTS string fields** per index.

If any one of these is exceeded, the batch fails as a whole. The most common limit to hit on long-prose corpora is the per-FTS-field 100 KB / 10,000-token cap on a single body field — chunking is the standard fix (see below).

### Dense-vector payload size

A high-dimensional dense field can silently turn a 50-doc batch into a 5–10 MB request, which the preview backend will reject wholesale. If every batch fails and the error message is opaque, the first thing to try is dropping the embedding dimension before debugging schema:

- **Gemini**: pass `config=types.EmbedContentConfig(output_dimensionality=768)`. The model uses Matryoshka representations, so smaller dimensions are valid truncations of the native output. 768 is usually a 4× payload reduction vs. the native 3072 and costs very little quality.
- **OpenAI `text-embedding-3-*`**: pass `dimensions=768` (or similar) to `embeddings.create`.
- **Pinecone hosted / fixed-dim models**: dimension is fixed; the only levers are `batch_size` (halve it to 25) and per-document body size.

## The async-indexing footgun

After `batch_upsert` returns, **your documents are written but not yet searchable.** The server builds inverted indexes for FTS fields and ANN graphs for vector fields in the background. A search query issued immediately will return empty matches. Schemas with multiple indexed fields (e.g. text + dense + sparse) may take slightly longer.

**Always poll with a deadline** before trusting the index:

```python
import time

deadline = time.time() + 300  # up to 5 minutes
while time.time() < deadline:
    resp = idx.documents.search(
        namespace=NAMESPACE, top_k=1,
        score_by=[{"type": "text", "field": "<any_fts_field>", "query": "<sentinel>"}],
        include_fields=[],   # required on every search; [] = ids + _score only
    )
    if resp.matches:
        print("Data is searchable.")
        break
    time.sleep(5)
    print("Not yet indexed, retrying...")
else:
    print("WARNING: Documents may not be fully indexed after 5 minutes.")
```

Pick a sentinel query likely to hit at least one document. For a typical corpus, a single common token works (e.g. `"book"` for a book-reviews corpus). For a small corpus, use a term you *know* appears in at least one document.

## Chunking oversized text

Per the public-preview docs (above), the per-FTS-field hard limits are 100 KB and 10,000 tokens. In practice, plan for the *token* limit kicking in first on natural prose (~5,000 English words at ~2 tokens each is the rough ceiling). Probe before ingesting at scale — chunk anything that approaches either bound, with safety margin.

**Strategy: probe first, then chunk if needed.**

1. Find the longest document in your corpus: `max(len(doc["body"]) for doc in docs)`.
2. Try upserting it as-is. If the upsert errors, chunk.

**Chunking pattern:**

```python
def chunk_text(text, max_chars=32_000):
    # Simple paragraph-aware chunking. Adjust the boundary for your corpus.
    paras = text.split("\n\n")
    chunks, cur = [], []
    cur_len = 0
    for p in paras:
        if cur_len + len(p) > max_chars and cur:
            chunks.append("\n\n".join(cur))
            cur, cur_len = [p], len(p)
        else:
            cur.append(p)
            cur_len += len(p)
    if cur:
        chunks.append("\n\n".join(cur))
    return chunks

docs = []
for doc_id, text, title in source:
    chunks = chunk_text(text)
    for i, chunk in enumerate(chunks):
        chunk_id = doc_id if i == 0 else f"{doc_id}#p{i + 1}"
        docs.append({
            "_id": chunk_id,
            "parent_doc_id": doc_id,    # duplicate identifying metadata across chunks
            "title": title,             # so title matches hit every chunk
            "body": chunk,
        })
```

Conventions:

- **Shared key prefix.** First chunk keeps the original `_id`; subsequent chunks append `#p2`, `#p3`. Easy to parse client-side.
- **Duplicate identifying metadata.** Fields like `title`, `parent_doc_id`, `url`, or whatever identifies the logical document should be present on every chunk so queries that filter or score against those fields work uniformly.
- **Deduplicate at query time.** After `documents.search`, group matches by `parent_doc_id` (or strip the `#p*` suffix from `_id`) and keep the highest-scoring chunk per parent. This preserves relevance ranking while collapsing duplicates in the UI.

## Updating documents

There is **no per-field update or merge** in `2026-01.alpha`. `documents.upsert` always replaces the entire document for a given `_id`. To update one field:

```python
fetched = idx.documents.fetch(
    namespace=NAMESPACE,
    ids=["doc-42"],
    include_fields=["*"],          # need the full doc to round-trip it
)
doc = fetched.documents["doc-42"].to_dict()
doc["category"] = "biography"      # patch in client code

idx.documents.upsert(namespace=NAMESPACE, documents=[doc])
```

If the document includes a dense vector, you re-upsert that vector verbatim. If it changes, embed the new content first.

## Deletes

`documents.delete` accepts either `ids: [...]` (1–1000 items) or `delete_all: true`. There is **no delete-by-filter** — to delete documents matching a metadata expression, search first to collect IDs, then pass them in:

```python
ids_to_kill = [
    m._id for m in idx.documents.search(
        namespace=NAMESPACE, top_k=1000,
        score_by=[{"type": "text", "field": "body", "query": "deprecated"}],
        filter={"category": {"$eq": "archive"}},
        include_fields=[],
    ).matches
]
idx.documents.delete(namespace=NAMESPACE, ids=ids_to_kill)
```

`delete_all=True` wipes the entire namespace. Use carefully.

## Integrating embedding providers

If your index has a dense or sparse vector field, you need embeddings. Three common paths:

### Pinecone hosted inference

Cleanest integration — no extra API keys, same client as the index.

```python
# Indexing side: use input_type="passage" for stored content
resp = pc.inference.embed(
    model="multilingual-e5-large",
    inputs=[doc["body"] for doc in batch],
    parameters={"input_type": "passage", "truncate": "END"},
)
embeddings = [e.values for e in resp.data]

# Query side: use input_type="query" for query strings
q_resp = pc.inference.embed(
    model="multilingual-e5-large",
    inputs=[user_query],
    parameters={"input_type": "query"},
)
q_emb = q_resp.data[0].values
```

The distinction between `input_type="passage"` (stored content) and `input_type="query"` (runtime queries) matters for models that encode them asymmetrically (`multilingual-e5-large` is one). For sparse learned embeddings like `pinecone-sparse-english-v0`, the same convention applies, and each embedding has `.sparse_indices` / `.sparse_values` rather than `.values`.

Batch size: ~96 inputs per `embed` call is the typical server limit. Loop in chunks:

```python
EMBED_BATCH = 96
embeddings = []
for i in range(0, len(docs), EMBED_BATCH):
    chunk = docs[i : i + EMBED_BATCH]
    resp = pc.inference.embed(
        model="multilingual-e5-large",
        inputs=[d["body"] for d in chunk],
        parameters={"input_type": "passage", "truncate": "END"},
    )
    embeddings.extend(e.values for e in resp.data)
```

### Generic pattern — any third-party provider

Wrap the provider-specific call in a thin adapter so ingestion logic doesn't know which provider is in use:

```python
def embed(content) -> list[float]:
    """Return a single dense embedding for a piece of content.

    `content` may be a string or a PIL.Image, depending on the provider.
    Swap the implementation to change providers without touching callers.
    """
    resp = provider.embed(content)
    return resp.values  # or resp.data[0].embedding, etc.

docs = [{"_id": d["id"], "body": d["text"], "embedding": embed(d["text"])} for d in source]
```

This adapter also gives you a single chokepoint for retries, rate-limit backoff, and caching — add them once in `embed()` rather than at every call site.

## Limits to be aware of

- **No bulk import (S3 import job)** for document-shaped indexes in `2026-01.alpha`. Load through `documents.upsert` / `documents.batch_upsert`.
- **No backup/restore.** If you need recoverability, snapshot your source data, not the index.
- **No CMEK projects** — indexes can't be created in CMEK-enabled projects.
- **Indexing latency**: documents become searchable in ≲1 minute typically; multi-field schemas can take slightly longer.

