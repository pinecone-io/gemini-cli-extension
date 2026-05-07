---
name: pinecone-full-text-search
description: Create, ingest into, and query a Pinecone full-text-search (FTS) index using the preview API (2026-01.alpha, public preview). Use when the user or agent asks to build a text search index on Pinecone, add dense or sparse vector fields, ingest documents, construct score_by clauses (text / query_string / dense_vector / sparse_vector), or compose with text-match filters ($match_phrase / $match_all / $match_any). Ships `scripts/ingest.py` for safe bulk ingestion (batch_upsert + error inspection + readiness polling); query construction is documented inline in this skill — write `documents.search(...)` calls directly, validated against `pc.preview.indexes.describe(...)` output.
---

# pinecone-full-text-search

> **Requires `pinecone` Python SDK ≥ 9.0** (`pip install pinecone>=9.0`). The FTS document-schema API lives under `pinecone.preview` and is incomplete or absent in earlier SDK builds. The packaged helper scripts pin `pinecone==9.0.0` via PEP 723 inline metadata; if you're writing your own code against this skill, pin v9 explicitly. The wire API version is `2026-01.alpha`.

> **Authoritative reference (last resort).** If you hit a question this skill and its `references/*.md` files don't answer, the official Pinecone FTS docs are at <https://docs.pinecone.io/guides/search/full-text-search>. Prefer this skill's content for anything covered here — the docs may describe surfaces (e.g. classic vector API) that don't apply to the document-schema FTS path. Consult the link only when you're genuinely stuck.

> **Tell the user up front:** "This skill ships a helper at `scripts/ingest.py` that handles bulk ingestion safely (batched upsert, error inspection, readiness polling). When we get to the ingest step, I'll use it." Surface this at the start of the conversation so the user knows the helper exists. Query construction is hand-written `documents.search(...)` per the **Querying** section below — there is no query helper.

A workflow skill for building a Pinecone full-text-search index with the preview API (`pinecone.preview`, API version `2026-01.alpha`, public preview as of April 2026). Covers schema design (text, dense vector, sparse vector, filterable metadata), ingestion (including async indexing and polling), and query construction (`text` / `query_string` / `dense_vector` / `sparse_vector` scoring; `$match_phrase` / `$match_all` / `$match_any` text-match filters; `$eq` / `$in` / `$gte` / `$exists` / `$and` / `$or` / `$not` metadata filters).

## Scope — this skill is for the document-schema FTS API only

This skill covers `pc.preview.indexes.create(..., schema=...)`, `pc.preview.index(name)`, `idx.documents.upsert(...)` / `idx.documents.batch_upsert(...)` / `idx.documents.search(...)`. If you find yourself reaching for any of the following, **stop** — those are different Pinecone APIs and this skill's guidance and helpers won't apply:

- **Classic vector / records API**: `pc.Index(name)`, `index.upsert(vectors=[...])` / `index.upsert_records(...)`, `index.query(vector=..., sparse_vector=...)`, `index.search_records(...)`, `pc.create_index(...)` with `ServerlessSpec`, the legacy `pinecone_text.sparse.BM25Encoder` for sparse-dense hybrid. For indexes WITHOUT a schema (raw vectors).
- **Integrated-embedding indexes**: `pc.create_index_for_model(...)` with `embed={...}`. Pinecone vectorizes text server-side. Different upsert/search shapes. Cannot be combined with `full_text_search` fields in the same index.

If the user already has a non-document-schema index, they can stand up a separate document-schema index alongside it — the two are independent — but you can't add FTS fields to a classic index after the fact.

## Querying — construct `documents.search(...)` calls

For any task that asks you to query an FTS index, you write a `documents.search(...)` call directly. The schema is authoritative — describe the index live before constructing the call so you know which fields are FTS-enabled, which are filterable, and which are vectors.

**Workflow:**

1. **Discover the schema.** Call `pc.preview.indexes.describe(<index>)` and read the `schema.fields` dict. Each field's class indicates its type (`PreviewStringField`, `PreviewIntegerField`, `PreviewDenseVectorField`, etc.); attributes tell you whether it's FTS-enabled (`full_text_search`), filterable, or carries a `dimension`. Skip this step only if you've already seen the schema in this conversation.
2. **Construct the call** matching the rules below — one scoring type per request, hard requirements in `filter`, ranking signals in `score_by`, `include_fields` explicit on every call.
3. **Execute** with `idx = pc.preview.index(name=<index>); resp = idx.documents.search(...)` and read `resp.matches`.

**Canonical shapes:**

```python
# Pure BM25 keyword search
resp = idx.documents.search(
    namespace="__default__",
    top_k=10,
    score_by=[{"type": "text", "field": "body", "query": "machine learning"}],
    filter={"year": {"$gt": 2024}, "category": {"$eq": "ai"}},  # optional
    include_fields=["*"],   # always pass explicitly
)

# Hybrid: dense ranking with a lexical filter (one type in score_by + filter narrows)
resp = idx.documents.search(
    namespace="__default__",
    top_k=10,
    score_by=[{"type": "dense_vector", "field": "embedding", "values": query_embedding}],
    filter={"body": {"$match_all": "TensorFlow"}, "year": {"$gt": 2024}},
    include_fields=["*"],
)
```

**Key rules** (the server enforces these; following them locally keeps the agent loop tight):

- `score_by` is a list of clauses, but **exactly one scoring type per request** (server rejects mixed types). Multi-field BM25 is the one exception: multiple `text` clauses, or one `query_string` with `fields: [...]`. To combine BM25 + dense signals, restrict the dense search with a text-match filter (`$match_all` / `$match_phrase` / `$match_any`); do NOT mix scoring types in `score_by`.
- `filter` keys are field names (must exist in schema and be filterable) OR logical operators (`$and`, `$or`, `$not`). Field values are operator dicts (`{"$gt": 5}`, NOT bare values).
- `include_fields` is required on every call. Pass `["*"]` for all stored fields, `[]` for ids+score only, or a list of names. Some SDK builds 400/422 if it's omitted.

**Clause shapes** (for `score_by`):

| `type` | Required keys | When to pick this |
|---|---|---|
| `text` | `field` (string FTS), `query` | Open-ended keyword search; BM25 ranking on one field |
| `query_string` | `query` (Lucene), `fields` optional | Lucene boost (`^N`), proximity (`~N`), cross-field boolean, phrase prefix |
| `dense_vector` | `field` (dense_vector), `values` (list of floats) | Semantic / mood / topic ranking |
| `sparse_vector` | `field` (sparse_vector), `sparse_values` ({indices, values}) | Custom sparse-encoder ranking |

`text` / `dense_vector` / `sparse_vector` use singular `field`. Only `query_string` accepts a `fields` array (and also accepts singular `field` as an alias). `sparse_vector` uses `sparse_values` (NOT `values`) — distinct from dense.

**Filter operators by field type:**

| Field type | Legal operators |
|---|---|
| `string` with FTS | `$match_phrase`, `$match_all`, `$match_any` |
| `string` filterable | `$eq`, `$ne`, `$in`, `$nin`, `$exists` |
| `string_list` filterable | `$in`, `$nin`, `$exists` |
| `float` filterable | `$eq`, `$ne`, `$gt`, `$gte`, `$lt`, `$lte`, `$exists` |
| `boolean` filterable | `$eq`, `$exists` |
| logical wrappers | `$and: [filters]`, `$or: [filters]`, `$not: filter` |

**Match shape on response:**

```python
for m in resp.matches:
    m._id        # document id
    m._score     # match score (NOT `score`); some older SDK builds may also surface `score`
    m.to_dict()  # full doc payload (when include_fields includes the field)
```

For deeper coverage — multi-field BM25, Lucene patterns, hybrid composition, RRF merges, common error symptoms — see `references/querying.md`. For schema field types and what they enable on the query side, see `references/schema-design.md`.

## Ingesting — use the packaged helper

For **any task that asks you to bulk-ingest a JSONL file into an existing FTS index**, the canonical path is to invoke the bundled helper, NOT to hand-write a Python script. **Do not read the script's source** — everything you need is in this section.

The script does three things bare-LLM ingest code reliably skips, each of which corresponds to a silent production failure:

1. **Bulk-upserts in batches.** No per-doc `upsert` loops.
2. **Inspects every batch result.** `batch_upsert` returns 202 even when individual documents fail; the failures live in `result.errors` / `result.has_errors`. Without inspection, "100 docs ingested" silently becomes "73 docs ingested + 27 lost."
3. **Polls until searchable.** After upsert, Pinecone is still building the inverted index. A `documents.search` call during that window returns empty. Without the poll, the user debugs their *query* code for an hour without finding the indexing race.

You provide a prepared, schema-conformant JSONL file and the index name; the script does the rest. Schema validation is upstream concerns (your prep pipeline, or `prepare_documents.py` when it lands) — `ingest.py` trusts what you hand it.

**Invocation:**

```bash
uv run --script .claude/skills/pinecone-fts-index/scripts/ingest.py \
  --data processed.jsonl \
  --index <index_name> \
  --sentinel-field <fts_field>
```

**Flags:**

| Flag | Short | Required | Purpose |
|---|---|---|---|
| `--data` | `-d` | yes | Path to JSONL file with prepared documents (one per line) |
| `--index` | `-i` | yes | Pinecone index name (must already exist) |
| `--sentinel-field` | `-f` | yes | An FTS-enabled field on the index, used for the readiness-poll query. Pick the longest free-text field on your schema. |
| `--namespace` | `-n` | no | Default `__default__` |
| `--batch-size` | `-b` | no | Default 100. **Reduce for large dense vectors.** A 50-doc batch with 3072-dim float vectors lands ~5-10 MB and can be rejected; drop to `--batch-size 50` (or lower) at high dimensions. |
| `--poll-deadline` | — | no | Default 300 (seconds). Time to wait for documents to become searchable before giving up. |
| `--sentinel` | `-s` | no | Token used for the readiness-poll query. Default: first whitespace-separated token of `doc[0][sentinel-field]`. |

**What the script prints:**

```
Loading processed.jsonl ...
Loaded 5000 document(s).
Sentinel: body='The'

Upserting in batches of 100 ...
  batch @     0:  100 docs in  0.42s  (total: 100/5000)
  batch @   100:  100 docs in  0.39s  (total: 200/5000)
  ...

Upsert complete: 5000 doc(s) in 21.4s.

Polling for searchability (deadline 300s) ...
Searchable after 12.3s (3 probe(s)).

Done — total 33.7s.
```

If a batch fails, the script prints every error message and exits non-zero. If the poll deadline expires, the script prints a hint about why (sentinel field isn't FTS-enabled, deadline too tight, docs structurally upserted but rejected by the inverted-index builder) and exits non-zero. **Don't suppress these errors** — they're surfacing real problems with the data or the index.

**When you should NOT use the script:**

- The user is doing per-doc patch updates (single-doc `documents.upsert` calls with selective fields). The script is for bulk loads, not per-record operations.
- The user is ingesting from a non-JSONL source (CSV, Parquet, Postgres dump). Convert to JSONL first; the script doesn't parse other formats.
- The user explicitly asks you to write the ingestion code from scratch (teaching context). Honor the request and follow the canonical pattern: `documents.batch_upsert` + `result.has_errors` inspection + `documents.search` polling with sentinel and deadline.

The script lives at `.claude/skills/pinecone-fts-index/scripts/ingest.py`. PEP 723 inline-metadata script — `uv run --script` installs `typer` and `pinecone` automatically on first invocation. No setup needed.

## Use cases

Three concrete shapes to model your task on. Match the user's request to the closest one and follow its steps; improvise if the task is genuinely a hybrid.

### UC-1: Index a new corpus end-to-end

**Trigger.** "Index this CSV / JSONL / folder for search," "build a search backend over [my articles / products / tickets / transcripts]," "make my [dataset] searchable."

**For unprocessed / messy data, load the onboarding walkthrough first.** If the user is showing up with raw data (unclear field types, possibly long text fields exceeding FTS limits, comma-separated tag strings, dates as strings, possibly duplicate IDs, etc.) and they haven't given you an explicit schema, **read `references/onboarding-walkthrough.md` and follow it stage-by-stage.** It's a conversational guide — meet the data, surface the processing decisions to the user, propose a schema, confirm before creating, then process+ingest+verify together. The walkthrough exists because schemas are immutable and "onboarding a new corpus" is a high-stakes flow that benefits from explicit user buy-in at each decision point.

If the user already gave you a clean JSONL + a schema spec, follow the abbreviated steps below.

**Steps (when data is already prepared and the schema is decided):**
1. Inspect the corpus shape — text fields, structured metadata, do you also need a vector? Match it to one of the canonical shapes in `references/schema-design.md` (articles, products, tickets, image library, code).
2. Pick analyzer settings on each text field — `language`, `stemming`, `stop_words`. Stemming on for long prose, off for proper nouns / identifiers.
3. Assemble the schema with `SchemaBuilder` and **confirm it with the user before calling `indexes.create`** — schemas are immutable in `2026-01.alpha`, so a wrong call costs a re-ingest.
4. Create the index, poll `describe()` until `status.ready: true`.
5. **Run `scripts/ingest.py --data <jsonl> --index <name> --sentinel-field <fts_field>`** — see the **Ingesting — use the packaged helper** section above. The script handles `batch_upsert` + per-batch error inspection + post-upsert readiness polling in one invocation. Don't hand-write the loop unless the user explicitly asks you to.
6. (The script polls automatically — by the time it exits cleanly, the index is searchable. If you skip the script and roll your own, you must poll `documents.search` with a sentinel query and a deadline; `batch_upsert` returning ≠ searchable.)
7. Validate with one or two probe queries against fields you know contain the sentinel content.

**Result.** A working `documents.search` call against the user's data, returning ranked matches.

### UC-2: Add a dense (or sparse) signal to a text-only corpus

**Trigger.** "Add semantic search," "add embeddings," "make this hybrid," or any prompt that describes a query pattern text alone can't serve (visual similarity, mood, cross-modal "looks like").

**Steps.**
1. Confirm the new signal represents a **modality or signal text can't express** — image / audio / external score, *or* a different corpus than the existing FTS field. Re-encoding the same text into a dense field is an anti-pattern (`references/schema-design.md` → "When to add a dense field at all").
2. Because schemas are immutable, **plan a new index, not a migration**. Get user confirmation before recreating.
3. Pick an embedding provider and pin its output dimension at schema time. Beware payload-size pitfalls at native dimensions — Gemini-3072 etc. need truncation (`references/ingestion.md` → "Dense-vector payload size").
4. Schema → create → wait Ready → ingest with embeddings inline or pre-cached.
5. Validate with a **hybrid query**: `dense_vector` score_by + text-match filter (`$match_phrase` / `$match_all`). That's the supported single-call cross-modal shape.

**Result.** One index, two retrieval shapes — pure text *and* dense+filter hybrid — both runnable without further setup.

### UC-3: Build a `documents.search` call from a natural-language user prompt (agent mode)

**Trigger.** Agent receives a user prompt like "find articles about machine learning that mention TensorFlow and were published after 2024" or "documents about climate policy ranked by similarity to this paragraph." The index already exists.

**Steps.**
1. **(Optional) Discover the schema** by calling `pc.preview.indexes.describe(<NAME>)` and reading `schema.fields`. Skip if you already know the field types from earlier in the conversation.
2. **Decompose the user's prompt** into `score_by` / `filter` shapes using the agent-mode decomposition table below. (Hard requirements → `filter`. Ranking signals → `score_by`. Always include `include_fields` explicitly.)
3. **Construct the `documents.search(...)` call** following the rules in the Querying section above — one scoring type per request, operator/field-type matching, `include_fields` always set.
4. **Execute** the call. The response carries `resp.matches`; iterate to get `m._id`, `m._score`, and field values via `m.to_dict()`. Use the matches in whatever shape the user asked for.
5. If results come back empty or wrong, walk the failure tree in `Common gotchas`.

**Result.** Live search results matching the user's intent.

**The four common UC-3 mistakes** to actively avoid:
- Mixing scoring types in `score_by` (server rejects). Put hard requirements in `filter`; rank by one signal in `score_by`.
- Putting hard requirements in `score_by` as BM25 terms instead of in `filter` as `$match_all` / `$match_phrase` (returns ranked results that don't *guarantee* the term is present).
- Operator/field-type mismatches (e.g. `$match_all` on a float field, `$gt` on a string field). Consult the operator table in the Querying section.
- Omitting `include_fields` (some SDK builds 400/422). Always pass it explicitly.

## Agent-mode query decomposition

Map user prompt cues to API shapes. Read top-down — identify the cue, copy the corresponding shape.

| User prompt cue | API shape |
|---|---|
| Open-ended keywords ("articles about machine learning", search-bar query) | `score_by=[{"type": "text", "field": "<field>", "query": "<terms>"}]` — BM25 token-OR |
| Exact phrase, drives ranking ("rank by 'beautifully written'") | `score_by=[{"type": "query_string", "query": '<field>:("phrase here")'}]` |
| Exact phrase, hard requirement ("must contain 'machine learning'") | `filter={"<field>": {"$match_phrase": "machine learning"}}` |
| Required tokens, any order ("must mention TensorFlow", "must be about Illinois") | `filter={"<field>": {"$match_all": "tokens space-separated"}}` — preferred over `query_string` `+token` because it's a true hard filter, doesn't contribute to score |
| At least one of these tokens ("contains AI or ML or robotics") | `filter={"<field>": {"$match_any": "AI ML robotics"}}` |
| Excluded tokens ("not about deprecated", "no opinion pieces") | `filter={"$not": {"<field>": {"$match_any": "deprecated opinion"}}}` — or `-token` inside `query_string` |
| Boolean / boost / slop / phrase-prefix ("weight 'eagle' 3x", "within N words") | `score_by=[{"type": "query_string", "query": '<expr with ^N / ~N / "…"*>'}]` — only Lucene supports these |
| Cross-field boolean ("title or body contains X") | `score_by=[{"type": "query_string", "query": 'title:(X) OR body:(X)'}]` |
| Numeric / date / range / boolean metadata ("after 2024", "rating > 4", "in stock") | `filter={"<field>": {"$gt": ..., "$gte": ..., "$eq": ..., "$exists": true}}` |
| Category / tag / list membership ("category = fiction", "tagged X") | `filter={"<field>": {"$in": [...]}}` (works on `string` and `string_list` filterable fields) |
| Semantic similarity / mood / topic ("articles about ML", "documents that feel sombre") | `score_by=[{"type": "dense_vector", "field": "<embedding_field>", "values": embed(<text>)}]` — requires a `dense_vector` field |
| Visual appearance / cross-modal text query against an image corpus | Same dense_vector shape, with the embedding model that produced the stored image vectors. Multimodal embedders (Gemini-2 etc.) map a text query into the image space. |
| Hybrid: lexical requirement + semantic ranking ("articles about ML that mention TensorFlow") | Lexical → `filter` (`$match_all` / `$match_phrase`); semantic → `score_by` (`dense_vector`). Single call. |

**Two structural rules the agent must enforce, no exceptions:**

- **One scoring type per request.** `score_by` accepts `text` / `query_string` / `dense_vector` / `sparse_vector`, but a request ranks by *one*. Don't mix dense + text in `score_by` — the server rejects it. Multi-field BM25 is the only "list" pattern that's allowed (multiple `text` clauses, or one cross-field `query_string`).
- **Hybrid = filter + score_by, not two `score_by` clauses.** When a prompt has both a lexical requirement and a semantic ranking signal, lexical goes in `filter` (via `$match_*` operators) and semantic goes in `score_by`. If both signals genuinely need to drive *ranking*, run two searches and merge IDs client-side.

## Workflow at a glance

Three phases. Each has its own reference file — consult it before writing code for that phase.

1. **Design the schema.** Decide which string fields are full-text-searchable, which are filterable metadata, whether you need a `dense_vector` field (and whether it earns its place), whether you also need a `sparse_vector` field, and which numeric / boolean / array filters to declare. Schemas are **fixed at index creation** in `2026-01.alpha` — plan carefully. → `references/schema-design.md`
2. **Ingest documents.** For bulk loads from a prepared JSONL, run the bundled `scripts/ingest.py` helper (it does `batch_upsert` + error inspection + readiness polling correctly by construction — see the **Ingesting — use the packaged helper** section above). For per-doc patch updates, hand-call `documents.upsert`. Either way, documents are indexed asynchronously after the HTTP call returns; `batch_upsert` returning 202 ≠ searchable. → `references/ingestion.md` for the canonical pattern in detail.
3. **Query the index.** A single search request ranks by **one** scoring type — pass exactly one of `text`, `query_string`, `dense_vector`, or `sparse_vector` in `score_by` (multi-field BM25 is supported via multiple `text` clauses or a cross-field `query_string`). Layer `filter={...}` for text-match (`$match_phrase` / `$match_all` / `$match_any`) and metadata filters (`$eq` / `$in` / `$gte` / `$exists` / `$and` / `$or` / `$not`). Control the response payload with `include_fields`. → `references/querying.md`

## Quick template

End-to-end skeleton for a minimal text + filterable-metadata index. Copy it and edit every spot marked `# TODO:`. The template deliberately omits external embedding calls so it stays generic; see `references/ingestion.md` for dense / sparse field patterns and embedding-provider integration, and `references/querying.md` for the four scoring shapes plus text-match and metadata filters.

```python
import time
from pinecone import Pinecone
from pinecone.preview import SchemaBuilder

INDEX_NAME = "my-fts-index"        # TODO: name your index (lowercase alphanumeric + hyphens, ≤45 chars)
NAMESPACE = "__default__"          # TODO: pick a namespace; auto-created on first upsert

pc = Pinecone()                    # reads PINECONE_API_KEY
# TODO: preprod backends require an x-environment header on the client:
#   pc = Pinecone(additional_headers={"x-environment": "preprod-aws-0"})

# 1. Schema — one FTS string field, one filterable string, one filterable float.
#    Field names must NOT start with `_` (reserved for `_id` / `_score`) or `$`
#    (reserved for filter operators), and are limited to 64 bytes.
schema = (
    SchemaBuilder()
    .add_string_field("body", full_text_search={"language": "en"})  # TODO: rename for your content
    .add_string_field("category", filterable=True)                   # TODO: any exact-match metadata
    .add_integer_field("year", filterable=True)                      # TODO: any numeric filter — emits `"type": "float"` on the wire
    .build()
)

# 2. Create the index. read_capacity defaults to {"mode": "OnDemand"}; pass
#    {"mode": "Dedicated", ...} only if you specifically want provisioned reads.
if not pc.preview.indexes.exists(INDEX_NAME):
    pc.preview.indexes.create(name=INDEX_NAME, schema=schema)

# 3. Wait for the index itself to become Ready.
while not pc.preview.indexes.describe(INDEX_NAME).status.ready:
    time.sleep(5)

idx = pc.preview.index(name=INDEX_NAME)

# 4. Upsert a single document. `_id` is required, every other field is optional.
#    upsert REPLACES the document on conflict — there is no per-field merge in 2026-01.alpha.
idx.documents.upsert(
    namespace=NAMESPACE,
    documents=[{
        "_id": "doc-1",
        "body": "Full-text search is great for keyword queries.",
        "category": "intro",
        "year": 2025.0,
    }],
)

# 5. Poll until the FTS side is searchable (upsert returns BEFORE docs are indexed).
deadline = time.time() + 300
while time.time() < deadline:
    resp = idx.documents.search(
        namespace=NAMESPACE, top_k=1,
        score_by=[{"type": "text", "field": "body", "query": "search"}],  # TODO: sentinel query likely to hit
        include_fields=[],          # required on every search; [] = lightest payload (ids + _score only)
    )
    if resp.matches:
        break
    time.sleep(5)

# 6. Search — text scoring composed with metadata filter.
resp = idx.documents.search(
    namespace=NAMESPACE,
    top_k=5,
    score_by=[{"type": "text", "field": "body", "query": "keyword queries"}],
    filter={"year": {"$gte": 2024}},        # TODO: adjust filter or drop it
    include_fields=["*"],                    # "*" = all stored fields; [] = `_id` + `_score` only
)
for m in resp.matches:
    print(m._id, getattr(m, "_score", getattr(m, "score", None)), m.to_dict())
```

## Common gotchas

- **One scoring type per search request.** `score_by` accepts `text`, `query_string`, `dense_vector`, or `sparse_vector` — but a request ranks by *one* type. Multi-field BM25 is fine (pass several `text` clauses, or a single cross-field `query_string`). To combine BM25 ranking with a `dense_vector` (or `sparse_vector`) signal, restrict the dense search with a text-match `filter` operator (`$match_phrase` / `$match_all` / `$match_any`) on the lexical field, *not* by mixing types in `score_by`. The "blend a dense vector and a text clause in `score_by`" pattern is rejected by the server.
- **Text-match filter operators are the cross-modal hinge.** `$match_phrase` (exact phrase), `$match_all` (every token, any order), `$match_any` (at least one token) are filter-side operators on `full_text_search` fields. Each takes a single string (max 128 tokens). They reuse the field's tokenizer / stemmer, compose under `$and` / `$or` / `$not`, and are the supported way to compose lexical pre-filtering with dense or sparse ranking. **Phrase slop (`"…"~N`), term boost (`^N`), and phrase prefix (`"… word"*`) are scoring-only — they live in `query_string`, not in `filter`.**
- **Preprod backends need `additional_headers={"x-environment": "..."}` on the `Pinecone()` client.** Missing the header lands you on prod and you'll see "index not found" / empty-result symptoms that look like code bugs but aren't.
- **`include_fields` is required on every `documents.search(...)` call.** When omitted, defaults to `[]` (`_id` + `_score` only). Pass `["*"]` for all stored fields or a list of names to project. Omitting it on some SDK builds yields `400` / `422` instead of the documented default; always pass it explicitly to avoid surprises.
- **Match score is `_score`; doc id is `_id`.** Public-preview docs return the system match score on the `_score` field so a user metadata field literally named `score` can coexist. Always prefer `_score` on read; some older SDK builds may still surface plain `score`, so for defensive code use `getattr(m, "_score", getattr(m, "score", None))`.
- **Reserved field names: leading `_` and `$`, max 64 bytes.** `_` is for system fields (`_id`, `_score`); `$` is for filter operators. Schema validation rejects names that violate either rule. Length cap is bytes, not characters — be careful with non-ASCII names.
- **Vector-field cardinality: at most one `dense_vector` and at most one `sparse_vector` per index** in `2026-01.alpha`. Multiple text fields are fine.
- **`batch_upsert` failures are silent by default.** The return value carries `has_errors`, `failed_batch_count`, and a list of `BatchError` objects with `error_message`. If you don't inspect them, you'll see "Uploaded 0 / N" and an indefinite "not yet indexed" poll — with the real cause (payload-too-large, schema mismatch, reserved field name) hidden. Always print `result.errors[*].error_message` before downstream steps.
- **Dense-vector payload size matters at batch time.** A 50-doc batch with 3072-dim float vectors lands around 5–10 MB and can be rejected by the preview backend. If every batch fails, try reducing the embedding dimension via your provider's truncation knob (e.g. Gemini's `output_dimensionality=768`) before debugging schema.
- **Async indexing: `batch_upsert` returning ≠ searchable.** The server builds inverted indexes in the background after the HTTP call returns. If you query immediately you'll see empty result sets. Always poll `documents.search` with a sentinel query and a deadline (pattern in `references/ingestion.md`).
- **String FTS field shape is `full_text_search={...}` (dict).** Pass `{}` to enable with all server defaults. **User-settable sub-fields:** `language`, `stemming`, `stop_words`. **Server-applied** (visible in `describe()` responses but NOT settable at index creation): `lowercase` (default `true`) and `max_token_length` (default `40`). Stemming is opt-in (default `false`); `stop_words` is opt-in (default `false`, opposite of pre-public-preview docs). The earlier SDK shape `full_text_searchable=True, language="en"` is legacy and should be avoided.
- **Schemas are fixed at index creation in `2026-01.alpha`.** Adding, removing, or retyping fields after creation is not supported. Changing dimension or metric on an existing vector field requires a new index. Plan the schema once.
- **No partial / per-field updates.** `documents.upsert` always replaces the entire document for a given `_id`. To update one field, fetch the doc, modify in client code, and upsert the full doc back under the same `_id`.
- **Document operations: search supports `filter`, fetch and delete do not.** Fetch is **ID-only** (`POST /documents/fetch` with `ids: [...]`); delete accepts only `ids` or `delete_all: true`. To act on a metadata expression, search first to collect IDs, then fetch or delete those IDs.
- **Namespaces auto-create on first upsert.** Pass any namespace string to `documents.upsert` / `batch_upsert` and the namespace is created on the fly; documents from different namespaces are fully isolated. Use `"__default__"` if you don't need partitioning. **Caveat:** the namespace management endpoints (`POST /namespaces`, `GET /namespaces`, `DELETE /namespaces/{namespace}`) and `describe_index_stats` are NOT yet supported on indexes with document schemas — you can write to a namespace, you just can't list / delete them via the API yet.
- **Document and request size limits** (preview): per-document max **2 MB**; per-request max **2 MB and 1000 documents**; per FTS-enabled `string` field max **100 KB and 10,000 tokens** (tokens > 256 bytes are truncated by the analyzer); per-document filterable metadata (everything *not* in an FTS field) max **40 KB**. A schema can declare up to **100 FTS string fields**. For long-prose corpora, chunk before ingest — see `references/ingestion.md`.
- **`score_by` clause shape — singular `field` is canonical for `text`/`dense_vector`/`sparse_vector`; only `query_string` takes a `fields` array.**
    - `text`: `{"type":"text", "field":"<fts_field>", "query":"<terms>"}`.
    - `query_string`: `{"type":"query_string", "query":"<lucene>", "fields":["<a>","<b>"]}` (the optional `fields` array; `query_string` also accepts a bare `"fields":"body"` string and the legacy `"field":"body"` as an alias).
    - `dense_vector`: `{"type":"dense_vector", "field":"<dense_field>", "values":[/*floats*/]}`.
    - `sparse_vector`: `{"type":"sparse_vector", "field":"<sparse_field>", "sparse_values":{"indices":[...],"values":[...]}}` — note `sparse_values` (NOT `values`) for sparse clauses.
- **Single-term prefix wildcards aren't supported.** `auto*` doesn't work in `query_string`; use phrase prefix (`"machine lea"*` — phrase must contain at least two terms, last term is matched as prefix).
- **Indexes can't be created in CMEK-enabled projects, no backup/restore, no fuzzy or regex search, no S3 bulk import** for document-shaped indexes in `2026-01.alpha`. If any of these are hard requirements, the public-preview FTS surface isn't yet ready.

## Extension points

Currently shipped under `scripts/`:

- `scripts/ingest.py` — bulk-ingest a prepared JSONL into an existing FTS index. Handles `batch_upsert` in safe-sized chunks, inspects every batch's `result.errors` and aborts loudly on failure, then polls `documents.search` with a sentinel + deadline until docs are searchable. Schema-agnostic: takes only `--data`, `--index`, `--sentinel-field`. Usage in **Ingesting — use the packaged helper** section above.

Query construction does NOT have a packaged helper — write `documents.search(...)` calls directly per the **Querying** section above.

