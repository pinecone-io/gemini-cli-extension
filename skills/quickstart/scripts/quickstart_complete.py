#!/usr/bin/env python3
# /// script
# dependencies = [
#   "pinecone>=8.0.0",
# ]
# ///

import os
from pinecone import Pinecone

api_key = os.environ.get("PINECONE_API_KEY")
if not api_key:
    raise ValueError("PINECONE_API_KEY environment variable not set")

pc = Pinecone(api_key=api_key, source_tag="pinecone_skills:index_quickstart")

# 1. Create a serverless index with an integrated embedding model
index_name = "quickstart"

if not pc.has_index(index_name):
    pc.create_index_for_model(
        name=index_name,
        cloud="aws",
        region="us-east-1",
        embed={
            "model": "llama-text-embed-v2",
            "field_map": {"text": "chunk_text"}
        }
    )

# 2. Upsert records
# Three distinct themes — notice the queries below use different words than the records.
# That's semantic search: finding meaning, not just matching keywords.
records = [
    # Health / feeling unwell
    {"_id": "rec1", "chunk_text": "I've been sneezing all day and my nose won't stop running.", "category": "health"},
    {"_id": "rec2", "chunk_text": "She stayed home with a pounding headache and a low-grade fever.", "category": "health"},
    {"_id": "rec3", "chunk_text": "He felt completely drained after waking up with a sore throat and chills.", "category": "health"},
    # Productivity / work
    {"_id": "rec4", "chunk_text": "She blocked off two hours in the morning to focus without interruptions.", "category": "productivity"},
    {"_id": "rec5", "chunk_text": "He finished all his tasks ahead of schedule by prioritizing the hardest ones first.", "category": "productivity"},
    {"_id": "rec6", "chunk_text": "Turning off notifications helped her get into a deep flow state.", "category": "productivity"},
    # Outdoors / nature
    {"_id": "rec7", "chunk_text": "A red fox darted across the trail and disappeared into the underbrush.", "category": "nature"},
    {"_id": "rec8", "chunk_text": "The hikers paused to watch a bald eagle circle lazily over the valley.", "category": "nature"},
    {"_id": "rec9", "chunk_text": "Fireflies lit up the meadow as the sun dipped below the treeline.", "category": "nature"},
]

dense_index = pc.Index(index_name)
dense_index.upsert_records("example-namespace", records)

# 3. Search records
# The query uses different words than the records — semantic search finds meaning, not keywords.
query = "feeling ill and run down"

results = dense_index.search(
    namespace="example-namespace",
    query={"top_k": 3, "inputs": {"text": query}}
)

print("Search results:")
for hit in results["result"]["hits"]:
    print(f"  id: {hit['_id']} | score: {round(hit['_score'], 2)} | text: {hit['fields']['chunk_text']}")

# 4. Search with reranking
reranked_results = dense_index.search(
    namespace="example-namespace",
    query={"top_k": 3, "inputs": {"text": query}},
    rerank={"model": "bge-reranker-v2-m3", "top_n": 3, "rank_fields": ["chunk_text"]}
)

print("\nReranked results:")
for hit in reranked_results["result"]["hits"]:
    print(f"  id: {hit['_id']} | score: {round(hit['_score'], 2)} | text: {hit['fields']['chunk_text']}")
