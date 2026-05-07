# Onboarding walkthrough — taking unprocessed data to a working FTS index

Load this file when the user shows up with **unprocessed data** and asks "make this searchable in Pinecone." The walkthrough is conversational on purpose — the goal is to help the user understand what decisions are being made, not to surprise them with a finished schema. **At each `ASK` beat, stop and wait for the user's response before proceeding.** Schemas are immutable; ingest is async; getting any of this wrong costs a re-ingest, so it's worth the chat round-trips.

## When this walkthrough applies

- The user has data sitting in a file (CSV, JSONL, JSON, Parquet, Postgres dump, etc.)
- The data hasn't been pre-cleaned for Pinecone — types may be off, fields may be messy, long bodies may exceed FTS limits, duplicates may exist
- The user said something like "make this searchable" / "build me a search index" / "put this in Pinecone"
- The user did NOT provide an explicit schema or describe one in detail

If the user already gave you a schema spec or a JSONL of clean records, skip to UC-1's standard steps in SKILL.md.

If the user has an integrated-embedding records index already and wants to add FTS to it, see the Scope section in SKILL.md — that's a different surface and you can't add FTS fields after the fact.

## Stage 1 — Meet the data

**Goal:** Both you and the user need to see the actual shape of the data before you can decide what to do with it.

**Action:**
1. Read the first 3-5 records of the file. Don't skim — look at field names, types, lengths, anything that looks off.
2. Summarize what you see in chat. Be concrete:
   - "Your file has N records."
   - "Each record has fields: A (string, ~X chars), B (string, up to Y chars), C (number), D (looks like a list/array)."
   - "I noticed: <one or two specific observations — duplicates, unusual values, field with very wide variance, etc.>"

**ASK the user** (one chat turn, numbered):
1. "Is this what you expected, or are there fields I should ignore / rename?"
2. "Are there any records that aren't representative? (e.g. test rows, debug entries)"
3. "Any fields that should be unique IDs? (Pinecone needs a `_id` per document; if your data already has a unique key like `slug` or `uuid`, we'll map it.)"

**Wait for the response.** If the user adjusts your understanding, re-read what you need and re-summarize. Don't move on until they've confirmed you understand the data.

## Stage 2 — Surface processing decisions

**Goal:** Most "unprocessed data" needs *some* transformation before it fits the FTS API. Surface the decisions so the user knows what you're going to do.

For each issue you saw in Stage 1, say what's happening and ask the user how to handle it. **Don't decide silently.** Common cases:

### Long FTS text fields

If any text field exceeds **100 KB** (or roughly **10,000 tokens** ≈ ~5,000 English words):
- Tell the user: "Field `body` has records up to N KB. The Pinecone FTS limit is 100 KB / 10,000 tokens per field. We'll need to chunk longer ones."
- **ASK**: "Want to chunk by paragraph (the standard for prose), by fixed character count, or by semantic units I can detect? When I chunk, the first sub-document keeps the original `_id` and subsequent ones get a suffix like `doc-42#p2`, `doc-42#p3` (the convention used by `scripts/ingest.py`). Sound OK?"

### Type mismatches (CSV/Excel/Postgres common cases)

If types don't match what an FTS schema would want:
- **Numbers stored as strings**: "Your `year` field is a string like `"2024"`. The schema needs a number. I'll coerce — but if any value can't be parsed, I'll abort and show you the offending row."
- **Booleans as strings**: same. "Convert `"true"` / `"false"` to booleans?"
- **Comma-separated tags**: "`tags` is a string `'classic,american'`. The schema would index tags as a list. I'll split on `,` — speak up if your data uses a different separator."
- **Dates / timestamps**: "Pinecone has no date type. We'll either store as ISO-8601 strings (filterable for exact match), or convert to epoch milliseconds (filterable as numeric). Which do you want?"

### Missing fields

If some records are missing fields others have:
- "About M of N records are missing `intro`. Do you want to: skip those records / store them with the field omitted / set a default?"

### Duplicates

If `_id` (or your nominated unique key) repeats:
- "I found K duplicate IDs. Default behavior is last-wins (the later record overwrites). Or I can: abort if duplicates exist / merge fields across duplicates / first-wins. Which?"

### Reserved field names

If any field starts with `_` or `$`:
- "Your data has a field called `_started_at` — Pinecone reserves leading-underscore names for system fields. I'll rename to `started_at` unless you want a different name."

**ASK** (one chat turn): present each decision as a numbered question. Wait for answers. Don't proceed until every decision has a confirmed answer.

## Stage 3 — Propose the schema

**Goal:** Translate the user's data + their answers from Stage 2 into a concrete Pinecone schema. Show it in chat as readable Python, with a one-line rationale per field.

**Action:** Write a chat message like:

> Based on what we've discussed, here's the schema I'd create:
>
> ```python
> SchemaBuilder()
>     # Searchable text — long prose, stemming on so "running" matches "ran"
>     .add_string_field("body", full_text_search={"language":"en", "stemming":True})
>     # Searchable text — short titles, stemming off (proper nouns shouldn't over-match)
>     .add_string_field("title", full_text_search={})
>     # Filter only — exact-match category like "fiction"
>     .add_string_field("category", filterable=True)
>     # Numeric range filter (e.g. year > 2024)
>     .add_integer_field("year", filterable=True)
>     # Tag filter — list membership ($in)
>     .add_string_list_field("tags", filterable=True)
>     .build()
> ```
>
> A few notes:
> - **No dense_vector field** — you said you don't have embeddings yet. We can add one later, but it requires creating a *new* index because schemas are immutable. Want to add a placeholder now and keep the door open?
> - **`year` uses `add_integer_field`** but Pinecone stores it as `float` on the wire. The naming is confusing but normal — there's no separate integer type.
> - **`tags`** will become `["a","b","c"]` after the comma-split we discussed.
>
> Schemas are immutable in `2026-01.alpha` — once we create this, changing it means re-creating the index and re-ingesting all the data.

**ASK** (one question this time): "Look right? Want to adjust anything before I create the index?"

**Wait.** Do not proceed until the user explicitly approves (`yes`, `looks good`, `go ahead`, `ship it`, etc.). If they ask for changes, revise the schema in chat, re-show, ask again.

## Stage 4 — Create the index

Once approved:
1. Write the Python (`create.py` or inline) using the approved schema.
2. Run it. Poll until `pc.preview.indexes.describe(name).status.ready: True`.
3. Tell the user when it's ready: "Index `<name>` created and ready. Now ingesting your data."

If creation fails for a reason you didn't anticipate (e.g. name conflict, region mismatch, CMEK restriction), tell the user the specific error and how to fix — don't auto-retry under a different name without asking.

## Stage 5 — Process and ingest

**Goal:** Actually transform the data per Stage 2 decisions and bulk-load.

**Action:**
1. Write a small processing script that applies the agreed transformations: type coercion, chunking, dedup, list splitting, etc. Save the result to `processed.jsonl`.
2. Show the user a summary: "Wrote N processed records (was M raw; X chunked / Y deduped / Z dropped). Sample record: `<first record>`."
3. **ASK** (only if any record was dropped or substantially changed): "Look right?" If they confirm, proceed.
4. Invoke `scripts/ingest.py --data processed.jsonl --index <name> --sentinel-field <your-longest-fts-field>`. The script handles `batch_upsert` + error inspection + readiness polling. Don't reimplement that loop.
5. Watch its output. If it fails, tell the user *what* it complained about (field type mismatch, payload size, etc.) — don't just say "ingest failed."

## Stage 6 — Verify together

**Goal:** Confirm the data is actually searchable. Don't trust polling alone — run a real query.

**Action:**
1. Pick a sentinel query you know should match a known record. E.g. for a corpus of book reviews, the first word of the first record's `body`; for a corpus with named entities, a known title or proper noun against the relevant FTS field.
2. Run a `documents.search(...)` call against the index — `score_by=[{"type":"text", "field":"<fts_field>", "query":"<sentinel>"}]`, `include_fields=["*"]`, `top_k=3`. See the **Querying** section in SKILL.md for the canonical shape.
3. Show the user the results: "Search returned K matches. Top match was `<id>` with score `<x>`."
4. If it didn't match what you expected, debug *with* the user — don't silently rerun. The async-indexing window may not have closed yet, OR your processing dropped a field, OR the user's expectation was off.

## Stage 7 — Hand off

**Goal:** Make sure the user can use the index without you.

Tell them:
1. **The index name and schema** in one line.
2. **How to query** — give them a copy-pasteable `idx.documents.search(...)` snippet shaped to their schema (one `score_by` clause + the `include_fields` they care about). Refer them to the **Querying** section in SKILL.md or `references/querying.md` for variations.
3. **How to ingest more** — `scripts/ingest.py` with the same `--sentinel-field` they should use.
4. **How to delete** — `pc.preview.indexes.delete("<name>")` when done.
5. **What's in the way of changing the schema** — recreate + re-ingest, no schema migration.

Optionally save a small `README.md` in the working directory with the same info, so they have it when they come back.

## Anti-patterns — don't do these

- **Don't decide silently.** Every decision in Stage 2 should be surfaced. If you assume a separator, a coercion, a dedup policy, you'll be wrong sometimes and the user won't know to push back.
- **Don't call `indexes.create()` without explicit approval** — schemas are immutable.
- **Don't write a giant pre-flight script** that does Stages 1-2 in code without ever showing the user. The point is the conversation, not the automation.
- **Don't skip Stage 6.** Polling says the index is "ready"; only a real query confirms the documents are there in the shape you expected.
- **Don't add a dense_vector field "just in case."** It commits the user to a specific embedding dimension forever — and if they don't have embeddings to ingest, the field is useless.
- **Don't promise reversibility.** Whenever you say "we can change this later," follow up with: "...by creating a new index and re-ingesting. There's no schema migration."

## Non-interactive runtimes

If you're running in a non-interactive harness (CI bot, batch processor, eval sandbox where the user can't respond), make best-effort decisions, document each one in chat or comments, and proceed. Document the assumptions clearly so a human reviewing later can spot them: "I picked stemming=on for `body` because it's long prose. I assumed comma-separated `tags`. I dropped duplicate `_id`s with last-wins." When in doubt, prefer the conservative choice (don't chunk if you're unsure how, don't coerce if the values look ambiguous).
