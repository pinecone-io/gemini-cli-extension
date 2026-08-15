# Querying

All reads on a Pinecone preview document index go through `idx.documents.search(...)` (ranked) or `idx.documents.fetch(...)` (direct, ID-only). The interesting shape is the **single** `score_by` clause and the `filter={...}` predicate — everything else is plumbing.

## The one-scoring-type rule

A single `documents.search` request ranks by **one** scoring type. `score_by` accepts a list, but every entry must share a type:

- Multiple `text` clauses (one per field) — that's how multi-field BM25 works.
- A single `query_string` clause (which can target multiple fields via `fields: [...]` or inline `field:term` syntax inside the Lucene expression).
- `dense_vector` clauses must appear alone.
- `sparse_vector` clauses must appear alone.
- You **cannot** blend types — no `text` + `query_string`, no `text` + `dense_vector`, no cross-type mix. The server rejects it.

To compose lexical and dense / sparse signals, put the lexical signal in `filter` via the text-match operators (`$match_phrase` / `$match_all` / `$match_any`) and let the vector clause in `score_by` do the ranking. That's the supported hybrid pattern in `2026-01.alpha`.

## `score_by` signal types

### 1. `text` — BM25 token-OR on a single text field

```python
resp = idx.documents.search(
    namespace=NAMESPACE,
    top_k=5,
    score_by=[{"type": "text", "field": "body", "query": "beautifully written"}],
    include_fields=["*"],
)
```

Tokenizes `query` with the field's analyzer, scores each matching document with a BM25 ranker over the inverted index, returns the top `top_k`. Multiple terms use **OR semantics** — documents matching any token participate, those matching more / rarer tokens score higher. Phrase constraints (adjacent words in order) are **not** supported here — use `query_string` with quotes, or a `$match_phrase` filter, for phrase semantics.

`field` is a **single string** (singular) naming an FTS-enabled `string` field — `text` clauses are scoped to one field at a time. For multi-field BM25, pass several `text` clauses (one per field) or use a `query_string` clause with a `fields` array (see Multi-field BM25 below).

### 2. `query_string` — Lucene syntax (boolean / phrase / boost / slop / prefix / cross-field)

```python
resp = idx.documents.search(
    namespace=NAMESPACE,
    top_k=5,
    score_by=[{
        "type": "query_string",
        "query": 'body:(classic AND ("masterpiece" OR timeless)) NOT body:boring',
    }],
    include_fields=["*"],
)
```

Supported operators (full table in the public-preview docs, summarized here):

| Operator       | Syntax              | Example                           |
|----------------|---------------------|-----------------------------------|
| Term           | `field:(word)`      | `body:(computers)`                |
| Multiple terms | `field:(a b)`       | `body:(machine learning)` (OR)    |
| Exact phrase   | `field:("words")`   | `body:("machine learning")`       |
| AND / OR / NOT | `AND` / `OR` / `NOT`| `body:(a AND (b OR c)) NOT d`     |
| Required       | `+term`             | `body:(+database search)`         |
| Excluded       | `-term`             | `body:(database -deprecated)`     |
| Phrase slop    | `"…"~N`             | `body:("fast search"~2)`          |
| Boost          | `term^N`            | `body:(machine^3 learning)`       |
| Phrase prefix  | `"… word"*`         | `body:("james w"*)`               |
| Cross-field    | `f1:(…) OR f2:(…)`  | `title:(quantum) OR body:(quantum machine)` |

**Cross-field clauses** are unique to `query_string` — they let one expression target multiple text-searchable fields with their own sub-clauses. Optionally pass a top-level `fields` array on the clause to restrict scope; omitted, the query runs against every text-searchable field in the schema.

```python
score_by=[{
    "type": "query_string",
    "fields": ["title", "body"],            # optional; restricts the query
    "query": 'title:(quantum)^2 OR body:("machine learning")',
}]
```

Single-term prefix wildcards (`auto*`) are **not** supported. Use phrase prefix instead: `"machine lea"*` (phrase must contain at least two terms; only the last is matched as prefix).

### 3. `dense_vector` — score against a stored dense vector

```python
resp = idx.documents.search(
    namespace=NAMESPACE,
    top_k=5,
    score_by=[{"type": "dense_vector", "field": "embedding", "values": query_vector}],
    include_fields=["title", "body"],
)
```

`field` is a single string (singular) naming a `dense_vector` field. `values` is a `list[float]` matching the field's declared dimension. Typically produced by embedding the user's query through the same (or a compatible) model at runtime. For text embedders with a passage/query distinction (e.g. `multilingual-e5-large`), use `input_type="query"` on the query side. Must appear alone in `score_by`.

### 4. `sparse_vector` — score against a stored sparse vector

```python
resp = idx.documents.search(
    namespace=NAMESPACE,
    top_k=5,
    score_by=[{
        "type": "sparse_vector",
        "field": "sparse_embedding",
        "sparse_values": {"indices": q.sparse_indices, "values": q.sparse_values},
    }],
    include_fields=["title", "body"],
)
```

Stored and queried as `{"indices": [...], "values": [...]}`. Hosted sparse models (e.g. `pinecone-sparse-english-v0`) return embeddings with `.sparse_indices` and `.sparse_values` ready to drop in. Must appear alone in `score_by`.

## Multi-field BM25

Two equivalent ways to score across multiple text fields in one request:

**Option A — multiple `text` clauses (one per field):**

```python
score_by=[
    {"type": "text", "field": "title", "query": q},
    {"type": "text", "field": "intro", "query": q},
    {"type": "text", "field": "body",  "query": q},
]
```

**Option B — one `query_string` cross-field expression:**

```python
score_by=[{
    "type": "query_string",
    "query": f'title:({q}) OR intro:({q}) OR body:({q})',
}]
```

Both reward documents that match in multiple fields. **`2026-01.alpha` weights every contributing field equally** — there is no per-clause weight parameter. To approximate weighting, use Option B with `^N` term boosts inside the query string (`title:({q})^3 OR body:({q})`).

## Filtering

Filters run **before** scoring — they shrink the candidate set, then the chosen `score_by` ranks survivors. Two families of operators.

### Text-match filters (on text-searchable fields)

These operate on `full_text_search`-enabled fields and reuse the field's tokenizer / stemmer. Each value is a single string (max 128 tokens). Not available inside `query_string` — they live in `filter`.

| Operator         | Semantics                                                    |
|------------------|--------------------------------------------------------------|
| `$match_phrase`  | Exact phrase match — tokens must be contiguous and in order. |
| `$match_all`     | All tokens present, in any order.                            |
| `$match_any`     | At least one token present.                                  |

```python
filter={"body": {"$match_phrase": "machine learning"}}      # exact phrase
filter={"body": {"$match_all":   "machine learning"}}      # both tokens, any order
filter={"body": {"$match_any":   "AI robotics"}}           # either token
```

These are the supported way to compose lexical pre-filtering with `dense_vector` (or `sparse_vector`) scoring — see "Cross-modal hybrid" below.

> **Scoring-only operators don't go in `filter`.** Phrase slop (`"…"~N`), term boost (`^N`), and phrase prefix (`"… word"*`) influence ranking, so they're available in `query_string` `score_by` but not in `filter`.

### Metadata filters (on `filterable: true` fields)

Standard comparison and membership operators — work on `string`, `string_list`, `float`, and `boolean` filterable fields.

| Operator | Example                                                     | Semantics                            |
|----------|-------------------------------------------------------------|--------------------------------------|
| `$eq`    | `{"category": {"$eq": "tech"}}`                             | Equals                               |
| `$ne`    | `{"category": {"$ne": "archive"}}`                          | Not equals                           |
| `$gt`    | `{"year": {"$gt": 2023}}`                                   | Greater than                         |
| `$gte`   | `{"year": {"$gte": 2023}}`                                  | Greater than or equal                |
| `$lt`    | `{"year": {"$lt": 2025}}`                                   | Less than                            |
| `$lte`   | `{"year": {"$lte": 2025}}`                                  | Less than or equal                   |
| `$in`    | `{"category": {"$in": ["a", "b"]}}`                         | In list (works on `string_list` too) |
| `$nin`   | `{"category": {"$nin": ["a", "b"]}}`                        | Not in list                          |
| `$exists`| `{"category": {"$exists": true}}`                           | Field has a value (`true`) or absent |

### Composing with `$and` / `$or` / `$not`

Multiple keys at the top level of a filter object are implicitly AND-ed. Use `$and`, `$or`, `$not` for explicit / nested composition. Text-match and metadata filters compose freely:

```python
filter={
    "$and": [
        {"body": {"$match_all": "federal reserve"}},     # text-match operator
        {"category": {"$eq": "finance"}},                # metadata operator
        {"year": {"$gte": 2024}},
        {"$not": {"tags": {"$in": ["opinion"]}}},
    ],
}
```

## Cross-modal hybrid: dense ranking + text-match filter

The supported way to compose lexical and dense signals in one request: dense (or sparse) `score_by`, plus a text-match `filter` that hard-restricts the candidate set to documents whose lexical field contains the right tokens / phrase.

```python
results = idx.documents.search(
    namespace=NAMESPACE,
    top_k=10,
    filter={"body": {"$match_phrase": "beautifully written"}},
    score_by=[{
        "type": "dense_vector",
        "field": "review_embedding",
        "values": embed("a moving family epic"),
    }],
    include_fields=["*"],
)
```

Read it top-down: only docs whose `body` contains the exact phrase `"beautifully written"`, ranked by dense-vector similarity to the embedding of "a moving family epic." One round trip, server-side hard filter, dense rerank.

When to use which text-match operator inside a hybrid query:

| Use `$match_phrase` when… | Use `$match_all` when…                       | Use `$match_any` when…                 |
|---------------------------|----------------------------------------------|----------------------------------------|
| Adjacency matters (named events, idioms, multi-word concepts where order is the signal). | All tokens are required but order is not (geography + topic, e.g. `"illinois cardinal"`). | At least one token is enough (broader recall — useful as a soft filter). |

## `include_fields` modes

`include_fields` controls what each match object carries back in the response.

| Value                        | Behaviour                                                      |
|------------------------------|----------------------------------------------------------------|
| *(omitted, or `null`)*       | Defaults to `[]` — `_id` and `_score` only.                    |
| `[]`                         | `_id` and `_score` only (lightest payload).                    |
| `["*"]`                      | All stored fields (including fields not declared in the schema).|
| `["field1", "field2"]`       | Only the listed fields (projection).                            |

**Always pass `include_fields` explicitly** on `documents.search`. Some SDK builds default to `[]`; some return `400` / `422` if it's missing. Being explicit avoids surprises and makes the call's intent obvious.

User metadata fields literally named `score` are returned alongside the system-owned `_score` match score — the leading underscore prevents collisions.

## Reading match objects

Match objects carry:

- `_id` (string) — document ID.
- `_score` (float) — system match score; **higher is better**.
- The fields requested via `include_fields`.

The `score` field name is reserved for **user metadata**; the system match score is always `_score`. Older SDK / backend builds may still emit unprefixed `score`; reading via `getattr(match, "_score", getattr(match, "score", None))` covers both.

## `documents.fetch` — direct retrieval, ID-only

Fetch is **ID-only** in `2026-01.alpha`. It does **not** accept a `filter`. To retrieve documents matching a metadata expression, search first to get IDs, then fetch:

```python
fetched = idx.documents.fetch(
    namespace=NAMESPACE,
    ids=["doc-1", "doc-2", "does-not-exist"],
    include_fields=["*"],
)
for doc_id, doc in fetched.documents.items():
    print(doc_id, doc.to_dict())
```

Missing IDs are silently omitted from the response (no error). `ids` accepts 1–1000 entries per call.

## `documents.delete` — by ID or `delete_all`

```python
# By IDs (1–1000 per call). Non-existent IDs are silently ignored.
idx.documents.delete(
    namespace=NAMESPACE,
    ids=["doc-1", "doc-2"],
)

# Wipe the entire namespace.
idx.documents.delete(
    namespace=NAMESPACE,
    delete_all=True,
)
```

Delete does **not** accept a `filter`. To delete documents matching a metadata expression, search first to collect IDs, then pass them to `delete`. Deletes are permanent within the namespace.

## Worked cross-modal example — "pick your signal" pattern

One index with two FTS text fields and one multimodal dense vector field. The dense field holds an embedding that lives in a shared text/image space (e.g. a Gemini multimodal embedding of each document's representative image). Because text and image share the space, a typed description can be embedded as text and scored against the stored image vectors.

### Schema

```python
schema = (
    SchemaBuilder()
    .add_string_field("title", full_text_search={"language": "en"})
    .add_string_field("body",  full_text_search={"language": "en", "stemming": True})
    .add_dense_vector_field("image_embedding", dimension=DIM, metric="cosine")
    .build()
)
```

### Three query modes against the same index

**1. Pure text — multi-field BM25 token-OR.**

```python
resp = idx.documents.search(
    namespace=NS,
    top_k=10,
    score_by=[
        {"type": "text", "field": "title", "query": "transformer architecture"},
        {"type": "text", "field": "body",  "query": "transformer architecture"},
    ],
    include_fields=["title", "body"],
)
```

**2. Exact phrase via `query_string`.**

```python
resp = idx.documents.search(
    namespace=NS,
    top_k=10,
    score_by=[{
        "type": "query_string",
        "query": 'body:("attention is all you need")',
    }],
    include_fields=["title", "body"],
)
```

**3. Pure dense — semantic query against stored vectors.**

```python
q_emb = embed("a paper introducing self-attention for sequence modeling")
resp = idx.documents.search(
    namespace=NS,
    top_k=10,
    score_by=[{"type": "dense_vector", "field": "image_embedding", "values": q_emb}],
    include_fields=["title", "body"],
)
```

**4. Hybrid — `$match_all` filter narrows; dense ranks.**

```python
q_emb = embed("self-attention for sequence modeling")
resp = idx.documents.search(
    namespace=NS,
    top_k=10,
    filter={"body": {"$match_all": "transformer"}},
    score_by=[{"type": "dense_vector", "field": "image_embedding", "values": q_emb}],
    include_fields=["title", "body"],
)
```

The same index supports all four modes; which one you want depends on whether the user's intent is keyword-driven (Mode 1), phrase-driven (Mode 2), appearance-driven (Mode 3), or "constrain by keyword, rank by appearance" (Mode 4). That's the pick-your-signal pattern — build the index once, vary the query shape per user intent.
