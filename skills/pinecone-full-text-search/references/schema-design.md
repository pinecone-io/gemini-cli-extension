# Schema design

Everything a Pinecone preview document index needs is declared up-front via `SchemaBuilder`. The schema pins which fields are searchable, which are filterable metadata, which hold vectors, and what their dimensions / metrics are. **Schemas are fixed at index creation in `2026-01.alpha`** — adding, removing, or retyping fields afterwards is not supported. Plan carefully.

## `SchemaBuilder` overview

```python
from pinecone.preview import SchemaBuilder

schema = (
    SchemaBuilder()
    .add_string_field("title", full_text_search={"language": "en"})
    .add_string_field("body",  full_text_search={"language": "en", "stemming": True})
    .add_string_field("category", filterable=True)
    .add_integer_field("year", filterable=True)              # emits `"type": "float"` on the wire
    .add_dense_vector_field("embedding",       dimension=1024, metric="cosine")
    .add_sparse_vector_field("sparse_embedding", metric="dotproduct")
    .build()            # terminal: returns the schema object you pass to indexes.create
)
```

`.build()` is the terminal call — every chain ends with it. The resulting schema is passed to `pc.preview.indexes.create(name=..., schema=schema, read_capacity=...)`. `read_capacity` defaults to `{"mode": "OnDemand"}` (auto-scaled shared reads); pass `{"mode": "Dedicated", "dedicated": {...}}` only if you specifically want provisioned read nodes.

## Field types at a glance

| Type            | Purpose                                    | Required options                          | How it's queried                          |
|-----------------|--------------------------------------------|-------------------------------------------|-------------------------------------------|
| `string` (text) | Full-text search (BM25 / Lucene)           | `full_text_search: {...}` (dict, may be `{}`) | `score_by` `text` or `query_string`; filter via `$match_phrase` / `$match_all` / `$match_any` |
| `string` (metadata) | Exact-match metadata filtering         | `filterable: true`                        | `filter` with `$eq` / `$in` / `$ne` / `$nin` / `$exists` |
| `string_list`   | Array-valued metadata filtering            | `filterable: true`                        | `filter` with `$in` / `$nin` (membership) |
| `float`         | Numeric metadata filtering                 | `filterable: true`                        | `filter` with `$eq` / `$gt` / `$gte` / `$lt` / `$lte` / `$in` / `$nin` |
| `boolean`       | Boolean metadata filtering                 | `filterable: true`                        | `filter` with `$eq` / `$exists`           |
| `dense_vector`  | ANN similarity search                      | `dimension`, `metric` (`cosine` / `dotproduct` / `euclidean`) | `score_by` `dense_vector` |
| `sparse_vector` | Sparse-vector lexical / hybrid scoring     | `metric` (typically `dotproduct`)         | `score_by` `sparse_vector`                |

Every field can also include an optional `description` string — surfaced by `DescribeIndex` and useful for agentic workflows where an LLM inspects the schema to decide how to query.

## Reserved field names

Field names must be unique, non-empty strings. Two hard rules:

- **Must not start with `_`** — reserved for system-managed fields (`_id`, `_score`).
- **Must not start with `$`** — reserved for filter operators.
- **Limited to 64 bytes** (bytes, not characters — non-ASCII names take extra space).

`_id` is required on every document. `_score` is the system match-score field name returned by `documents.search`. A user metadata field literally named `score` is allowed and won't collide with `_score`.

## String fields — text vs. metadata

A single `string` field is *either* full-text-search (BM25 / Lucene scoring + text-match filters) **or** filterable metadata (exact-match), never both. If you need both surfaces for the same logical content, duplicate it into two differently-configured fields.

### Full-text-searchable string

```python
.add_string_field("body", full_text_search={"language": "en", "stemming": True})
```

`full_text_search` takes a dict. Pass `{}` for all server defaults; populate it with any of:

- `language` (string, default `"en"`) — selects the analyzer (tokenizer + stemmer + stopword set). Supported short codes: `ar`, `da`, `de`, `el`, `en`, `es`, `fi`, `fr`, `hu`, `it`, `nl`, `no`, `pt`, `ro`, `ru`, `sv`, `ta`, `tr`. Full names are also accepted (e.g. `"english"`, `"french"`, `"arabic"`). Stop-word lists are available for most languages but a few are tokenize/stem only (no stop_word filtering even when `stop_words: true` is set) — `ar`, `da`, `de` are notable cases; `en`, `es`, `fr` etc. have full stop-word support.
- `stemming` (boolean, default `false`) — if `true`, applies the language's stemmer so `running` matches `runs`.
- `stop_words` (boolean, default `false`) — if `true`, the analyzer's stopword set is filtered out at index and query time.
- `lowercase` (boolean, default `true`, server-applied) — case-insensitive matching.
- `max_token_length` (int, default `40`, server-applied) — discards excessively long tokens.

Heuristic on stemming: turn it on for long prose fields where morphological variants of a root should match (`running` ~ `runs` ~ `ran`); leave off for short / identifier fields like titles, tags, or proper nouns where stemming would over-match (a book titled `Running` probably shouldn't also match the query `ran`). Typical pattern: stemming on for `body`, off for `title` / proper-noun fields.

Enables, on `field_name`:
- BM25 token scoring with `score_by=[{"type": "text", "field": "field_name", "query": "..."}]`.
- Lucene scoring with `score_by=[{"type": "query_string", "query": "field_name:(a AND (b OR c)) NOT field_name:d"}]`.
- Phrase / token filters: `filter={"field_name": {"$match_phrase": "..."}}`, `{"$match_all": "..."}`, `{"$match_any": "..."}`.

### Filterable-only string

```python
.add_string_field("category", filterable=True)
```

Stored verbatim, not tokenized, not text-scored. Enables exact-match filtering: `{"category": {"$eq": "fiction"}}`, `{"category": {"$in": ["fiction", "biography"]}}`, `{"category": {"$exists": true}}`.

## Numeric, boolean, and array metadata

```python
.add_integer_field("year", filterable=True)                              # wire type: "float"
.add_custom_field("featured", {"type": "boolean", "filterable": True})  # no add_boolean_field helper in v9
.add_string_list_field("tags", filterable=True)
```

- **`float`** is the only numeric wire type — there is no separate integer type. The SchemaBuilder helper is misleadingly named `add_integer_field` but emits `{"type": "float", "filterable": ...}`. Supports `$eq`, `$ne`, `$gt`, `$gte`, `$lt`, `$lte`, `$in`, `$nin`, `$exists`.
- **`boolean`** has no dedicated builder helper in pinecone v9 — declare via `add_custom_field("name", {"type": "boolean", "filterable": True})`. Supports `$eq` and `$exists`.
- **`string_list`** supports `$in` / `$nin` membership semantics — handy for tag-style metadata.

All filter operators compose under `$and`, `$or`, `$not`. Multiple keys at the top level of `filter` are combined with implicit AND.

> **SchemaBuilder helper-name pitfall** (pinecone v9): `add_integer_field()` produces `{"type": "float"}`, not a separate integer type. The class name in `describe()` responses is also `PreviewIntegerField`, but the wire/server type is `"float"`. Use `add_integer_field` for any numeric metadata; use `add_custom_field` with an explicit `{"type": "boolean", ...}` dict for booleans.

> **Forward-looking note.** In the public preview, metadata fields you send at upsert time are auto-indexed for filtering even if not declared in the schema. In a future release, only schema-declared fields with `filterable: true` will be indexed. Declare your metadata fields in the schema today to be future-proof.

> **Metadata size limit.** Filterable metadata on a single document is capped at **40 KB** combined (everything that's not in an FTS-enabled `string` field). FTS-enabled `string` fields don't count toward this — they have their own per-field limit (100 KB / 10,000 tokens, see `references/ingestion.md`).

## Dense vector fields

```python
.add_dense_vector_field("embedding", dimension=1024, metric="cosine")
```

- `dimension` must match whatever embedding model you'll store. If the model is chosen at runtime, query its default dimension first (e.g. `pc.inference.get_model(model="multilingual-e5-large").default_dimension`) and pass that in.
- `metric` is one of `"cosine"`, `"dotproduct"`, `"euclidean"`. Pick the metric the embedding provider recommends — most text embedders use cosine.
- Scored at query time with `score_by=[{"type": "dense_vector", "field": "embedding", "values": [...]}]`.

**At most one `dense_vector` field per index** in `2026-01.alpha`. If you need two semantically distinct dense signals, you need two indexes.

## Sparse vector fields

```python
.add_sparse_vector_field("sparse_embedding", metric="dotproduct")
```

- No `dimension` — sparse vectors are variable-length.
- `metric="dotproduct"` is the standard choice for learned sparse embeddings (e.g. `pinecone-sparse-english-v0`).
- Stored and queried as `{"indices": [...], "values": [...]}`; query side: `score_by=[{"type": "sparse_vector", "field": "sparse_embedding", "sparse_values": {"indices": [...], "values": [...]}}]`.

**At most one `sparse_vector` field per index** in `2026-01.alpha`.

## When to add a dense field at all

This is the key design question when the index already has FTS fields. **Only add a dense vector field when it represents a modality or signal that FTS cannot express.** Examples of justified dense fields:

- An **image embedding** over pictures associated with each document — visual appearance is not text.
- An **audio embedding** over voice clips or music — timbre and melody are not text.
- An **external ranking-model score** pre-computed and stored as a 1-D "vector" for sort purposes.
- A **semantic text embedding over a different corpus** than the one in the FTS field — e.g. the FTS field holds the product description, the dense field holds an embedding of the seller's support-ticket history for that product. Different data, different signal.

Anti-pattern: **re-encoding text that already lives in an FTS field on the same index.** Indexing the `body` string as FTS *and* embedding that same `body` into a dense text vector on the same index is redundant modeling, not an additive signal. FTS already gives you lexical retrieval; adding a dense re-encoding only pays off when the lexical signal is demonstrably insufficient (typically: very large corpus, very semantic queries, and you've measured the gap).

## Multi-field text design heuristics

When a document has a natural hierarchy (title → intro → body, or summary → transcript, or headline → lede → article), splitting across FTS fields enables two things you can't get from one blob:

1. **Per-field scoring.** A match on `title` is almost always a stronger signal than a match on `body`. With separate fields you can search just the title, just the body, or blend them at query time by listing each as its own `score_by` entry (see `references/querying.md` — multi-field BM25).
2. **Multi-field blended relevance.** Passing `score_by=[{text, title, q}, {text, intro, q}, {text, body, q}]` rewards documents that match in multiple fields. (`2026-01.alpha` weights every contributing field equally — no per-clause weight parameter.)

Keep it a single field when:

- The content has no natural subdivision (a tweet, a log line, a chat message).
- You will never want per-field weighting at query time.
- Your documents are short enough that inter-field distinctions are noise.

## Schemas are fixed at creation

`2026-01.alpha` does **not** support schema migration. You cannot:

- Add a new field after creation.
- Remove an existing field.
- Change a field's type or sub-config (e.g. flip a filterable string to FTS, toggle stemming, change dense vector dimension).

The supported workaround is to create a new index with the desired schema and reindex documents (the document set is small enough at preview-launch scale that this is usually painless). Existing pre-public-preview indexes from earlier API versions cannot be backfilled with a 2026-01.alpha schema.

## `description` for agentic / LLM-driven workflows

Each field accepts an optional `description` string:

```python
.add_string_field(
    "body",
    full_text_search={"language": "en", "stemming": True},
    description="Full article text. Use for keyword searches, narrative phrases, and topical queries.",
)
```

Returned by `DescribeIndex`. Useful when an LLM is choosing how to query: it can read the descriptions and pick the right field + operator without hard-coded prompt engineering.
