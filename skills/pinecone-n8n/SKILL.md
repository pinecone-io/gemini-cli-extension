---
name: pinecone-n8n
description: Build n8n workflows using the Pinecone Assistant node or Pinecone Vector Store node. Use when building RAG pipelines, chat-with-docs workflows, configuring Pinecone nodes in n8n, troubleshooting Pinecone n8n nodes, or asking about best practices for Pinecone in n8n.
allowed-tools: Write
---

# Pinecone n8n Workflow Skill

This skill helps you build n8n workflows with Pinecone nodes following best practices. It covers two Pinecone nodes:
- **Pinecone Assistant** (`@pinecone-database/n8n-nodes-pinecone-assistant`) — recommended for most use cases
- **Pinecone Vector Store** (`@n8n/n8n-nodes-langchain.vectorStorePinecone`) — for advanced control

**Core rule:** Always use the node's built-in resources and operations. Never suggest using the HTTP node to call the Pinecone REST API directly.

---

## Step 1: Understand the user's scenario

Ask the user what they're trying to do:
- Build a new workflow from scratch
- Configure or understand a specific Pinecone node
- Debug a workflow that isn't working
- Review an existing workflow for best practices

---

## Step 2: Node selection (for new workflows and configuration questions)

Always present the Pinecone Assistant node as the recommended choice first. Do NOT skip this step based on your own inference about which node fits better — even if the use case mentions specific triggers (Google Drive, webhooks, etc.) or file types (text, markdown, PDF), those details do not determine which node to use.

**Only skip this step if:**
- The user explicitly names a specific node (e.g. "I want to use the Vector Store node", "help me set up pineconeAssistant")
- The user is debugging or configuring an existing workflow that already has a specific Pinecone node in it

**If the user has not named a node, always ask or recommend the Assistant node first.** If the user said "use defaults" or you cannot ask, default to the Pinecone Assistant node and proceed with the Assistant path.

Ask the user which node they want to use, presenting these two options:

**Pinecone Assistant (Recommended)**
- Fully managed RAG — Pinecone handles chunking, embedding, and indexing automatically
- Built-in citations with file names and URLs
- Simpler setup: no embedding model or text splitter needed in n8n
- Great for: document Q&A, chat with files, knowledge base search

**Pinecone Vector Store**
- Full control over embedding model, chunking strategy, and metadata
- Works with any embedding model (OpenAI, Cohere, HuggingFace, etc.)
- Required when: you need custom embeddings, have an existing Pinecone index, need metadata filtering, or need fine-grained control over chunking

---

## Pinecone Assistant Node — Best Practices and Workflow Generation

### Node package names
- File operations (upload, list, delete): `@pinecone-database/n8n-nodes-pinecone-assistant.pineconeAssistant`
- Chat/retrieval as AI Agent tool: `@pinecone-database/n8n-nodes-pinecone-assistant.pineconeAssistantTool`

### Prerequisites
- Create a Pinecone Assistant in the Pinecone Console at https://app.pinecone.io/organizations/-/projects/-/assistant before running the workflow
- Set up a Pinecone credential in n8n with your API key

### Workflow architecture
The standard pattern is a two-phase workflow:

**Phase 1 — Ingestion** (run once or on a schedule):
```
Manual Trigger → Set file URLs → Split Out → HTTP Request (download) → Pinecone Assistant (uploadFile)
```

**Phase 2 — Chat**:
```
Chat Trigger → AI Agent ← Pinecone Assistant Tool (connected as ai_tool)
                        ← OpenAI Chat Model (connected as ai_languageModel)
```

### Key configuration rules
1. **assistantData parameter**: Always include BOTH `name` and `host` fields:
   ```json
   {"name": "your-assistant-name", "host": "https://your-assistant-host.pinecone.io"}
   ```
   Find your assistant's host in the Pinecone Console: open the assistant detail page and copy the host URL (format: `https://<region>-data.<subdomain>.pinecone.io`).
2. **sourceTag**: Always include in `additionalFields`:
   ```json
   {"sourceTag": "n8n:n8n_nodes_pinecone_assistant:pinecone_n8n_skill"}
   ```
3. **Connection type**: The Assistant Tool connects to the AI Agent via the `ai_tool` connection — NOT `main`
4. **externalFileId**: Set this to the file URL expression so Pinecone stores it as a reference for citations
5. **Credential**: Use `pineconeApi` credential type for both node variants
6. **File metadata on upload**: Add key-value metadata via `additionalFields.metadata.metadataValues` — an array of `{"key": "...", "value": "..."}` objects. The `externalFileId` is automatically added to metadata; do not include it manually. Example:
   ```json
   "additionalFields": {
     "metadata": {"metadataValues": [{"key": "department", "value": "legal"}]}
   }
   ```
7. **Metadata filtering on listFiles**: Use `additionalFields.metadataFilter.metadataValues` (same `{key, value}` array) for simple equality filters, or `additionalFields.advancedMetadataFilter` (a JSON string) for operators like `$or`, `$ne`, `$in`. Cannot set both at once. Example simple filter:
   ```json
   "additionalFields": {
     "metadataFilter": {"metadataValues": [{"key": "department", "value": "legal"}]}
   }
   ```
8. **Multimodal PDF upload**: Set `additionalFields.multimodalFile: true` on the `uploadFile` node when the PDF contains images or charts that should be indexed for visual retrieval. This is required for images to be retrievable later — it is not the default.

### Generating workflow JSON for the Assistant path

Build the workflow to match what the user actually describes — their triggers, models, data sources, and structure. Ask about anything structurally significant they haven't mentioned. Only fall back to the defaults below when the user hasn't specified a value:
- Assistant name: `n8n-assistant` (use `n8n-assistant-1`, `n8n-assistant-2`, etc. for multiples; must match an existing assistant in the Pinecone Console)
- File URLs: sample Pinecone release notes PDFs
- LLM model: `gpt-5-mini`
- System message: generic prompt about retrieving from the assistant with citations

The JSON below is a **reference configuration** showing correct parameter values, required fields, and connection types for each node. Use it as a guide for how to configure the nodes — not as a template to copy verbatim. Placeholders to substitute:
- `[ASSISTANT_NAME]` — assistant name
- `[ASSISTANT_HOST]` — assistant host URL from the Pinecone Console (e.g. `https://your-assistant-host.pinecone.io`)
- `[USER_FILE_URLS_ARRAY]` — JSON array of file URL strings, e.g. `["https://example.com/doc.pdf"]`
- `[USER_MODEL]` — LLM model name, e.g. `gpt-5-mini`
- `[USER_TOPIC]` — short description of what the assistant knows, for the system message

```json
{
  "nodes": [
    {
      "parameters": {
        "options": {
          "systemMessage": "You are a helpful assistant. Use the Pinecone Assistant Tool to retrieve data about [USER_TOPIC]. Include the file name and file url in citations wherever referenced in output."
        }
      },
      "type": "@n8n/n8n-nodes-langchain.agent",
      "typeVersion": 2.2,
      "position": [2208, 784],
      "id": "e4c65881-120c-4a7c-854b-138611c8dfa3",
      "name": "AI Agent"
    },
    {
      "parameters": {
        "model": {"__rl": true, "mode": "list", "value": "[USER_MODEL]"},
        "options": {}
      },
      "type": "@n8n/n8n-nodes-langchain.lmChatOpenAi",
      "typeVersion": 1.2,
      "position": [2144, 1008],
      "id": "b3ea858d-b62d-4022-8241-8872e403839a",
      "name": "OpenAI Chat Model"
    },
    {
      "parameters": {
        "content": "## 1. Upload files to Pinecone Assistant",
        "height": 384,
        "width": 1104,
        "color": 7
      },
      "type": "n8n-nodes-base.stickyNote",
      "position": [1616, 288],
      "typeVersion": 1,
      "id": "9cfcdb71-2986-47a3-8f03-250fcab1048d",
      "name": "Sticky Note1"
    },
    {
      "parameters": {
        "content": "## 2. Chat with your docs",
        "height": 512,
        "width": 1104,
        "color": 7
      },
      "type": "n8n-nodes-base.stickyNote",
      "position": [1616, 688],
      "typeVersion": 1,
      "id": "d7f2f4b8-2e45-4902-8949-202b8b2c699b",
      "name": "Sticky Note2"
    },
    {
      "parameters": {"options": {}},
      "type": "@n8n/n8n-nodes-langchain.chatTrigger",
      "typeVersion": 1.3,
      "position": [1840, 784],
      "id": "4d2a6aa1-ca4d-4165-a635-7ef53084636b",
      "name": "Chat input",
      "webhookId": "4672d1f8-d2bb-4059-8761-7aa5792814c0"
    },
    {
      "parameters": {},
      "type": "n8n-nodes-base.manualTrigger",
      "typeVersion": 1,
      "position": [1760, 432],
      "id": "3e9529b4-d0ae-4ea8-9d27-c96e7cbd6ad9",
      "name": "When clicking 'Execute workflow'"
    },
    {
      "parameters": {
        "assignments": {
          "assignments": [
            {
              "id": "d0e724df-685f-4661-b2ec-3cdd3c2ba0f1",
              "name": "urls",
              "value": "[USER_FILE_URLS_ARRAY]",
              "type": "array"
            }
          ]
        },
        "options": {}
      },
      "type": "n8n-nodes-base.set",
      "typeVersion": 3.4,
      "position": [1920, 432],
      "id": "6b409421-2270-497e-a7fd-b382d192314c",
      "name": "Set file urls"
    },
    {
      "parameters": {"fieldToSplitOut": "urls", "options": {}},
      "type": "n8n-nodes-base.splitOut",
      "typeVersion": 1,
      "position": [2080, 432],
      "id": "e73f6f2c-4d20-48cb-b132-551ff9c3dd61",
      "name": "Split to list"
    },
    {
      "parameters": {
        "url": "={{ $json.urls }}",
        "options": {"response": {"response": {"responseFormat": "file"}}}
      },
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [2240, 432],
      "id": "a58f8e1c-943b-4a24-8746-477ed9912ad4",
      "name": "Download file"
    },
    {
      "parameters": {
        "resource": "file",
        "operation": "uploadFile",
        "assistantData": "{\"name\":\"[ASSISTANT_NAME]\",\"host\":\"https://[ASSISTANT_HOST]\"}",
        "externalFileId": "={{ $('Split to list').item.json.urls }}",
        "additionalFields": {"sourceTag": "n8n:n8n_nodes_pinecone_assistant:pinecone_n8n_skill"}
      },
      "type": "@pinecone-database/n8n-nodes-pinecone-assistant.pineconeAssistant",
      "typeVersion": 1.2,
      "position": [2416, 432],
      "id": "196122df-d2b2-43e4-9f8d-710aedb595a6",
      "name": "Upload file to Assistant"
    },
    {
      "parameters": {
        "assistantData": "{\"name\":\"[ASSISTANT_NAME]\",\"host\":\"https://[ASSISTANT_HOST]\"}",
        "additionalFields": {"sourceTag": "n8n:n8n_nodes_pinecone_assistant:pinecone_n8n_skill"}
      },
      "type": "@pinecone-database/n8n-nodes-pinecone-assistant.pineconeAssistantTool",
      "typeVersion": 1.2,
      "position": [2368, 992],
      "id": "c3ba53e9-511d-47e7-b7fb-38bb093d279f",
      "name": "Get context from Assistant"
    }
  ],
  "connections": {
    "OpenAI Chat Model": {
      "ai_languageModel": [[{"node": "AI Agent", "type": "ai_languageModel", "index": 0}]]
    },
    "Chat input": {
      "main": [[{"node": "AI Agent", "type": "main", "index": 0}]]
    },
    "When clicking 'Execute workflow'": {
      "main": [[{"node": "Set file urls", "type": "main", "index": 0}]]
    },
    "Set file urls": {
      "main": [[{"node": "Split to list", "type": "main", "index": 0}]]
    },
    "Split to list": {
      "main": [[{"node": "Download file", "type": "main", "index": 0}]]
    },
    "Download file": {
      "main": [[{"node": "Upload file to Assistant", "type": "main", "index": 0}]]
    },
    "Get context from Assistant": {
      "ai_tool": [[{"node": "AI Agent", "type": "ai_tool", "index": 0}]]
    }
  },
  "pinData": {},
  "meta": {"templateCredsSetupCompleted": false}
}
```

### Other Pinecone Assistant operations

#### Upload File vs Update File — choosing the right operation

| Scenario | Operation to use |
|---|---|
| File is guaranteed to be new (never ingested before) | `uploadFile` |
| File may already exist in the assistant (re-ingestion, scheduled refresh) | `updateFile` |

`updateFile` is idempotent: it finds all files with the matching `externalFileId`, deletes them, then uploads the new version. If no file exists with that ID it behaves exactly like `uploadFile`. Use `updateFile` whenever a workflow may run more than once on the same source files.

Parameters for `updateFile` are identical to `uploadFile`: `assistantData`, `externalFileId`, `inputDataFieldName`, and all `additionalFields` including `metadata`, `multimodalFile`, and `sourceTag`.

```json
{
  "parameters": {
    "resource": "file",
    "operation": "updateFile",
    "assistantData": "{\"name\":\"[ASSISTANT_NAME]\",\"host\":\"https://[ASSISTANT_HOST]\"}",
    "externalFileId": "={{ $('Split to list').item.json.urls }}",
    "additionalFields": {"sourceTag": "n8n:n8n_nodes_pinecone_assistant:pinecone_n8n_skill"}
  },
  "type": "@pinecone-database/n8n-nodes-pinecone-assistant.pineconeAssistant",
  "typeVersion": 1.2
}
```

#### List Files
Use `resource: "file", operation: "listFiles"` to retrieve files, optionally filtered by metadata.

```json
{
  "parameters": {
    "resource": "file",
    "operation": "listFiles",
    "assistantData": "{\"name\":\"[ASSISTANT_NAME]\",\"host\":\"https://[ASSISTANT_HOST]\"}",
    "additionalFields": {
      "sourceTag": "n8n:n8n_nodes_pinecone_assistant:pinecone_n8n_skill",
      "metadataFilter": {
        "metadataValues": [{"key": "department", "value": "legal"}]
      }
    }
  },
  "type": "@pinecone-database/n8n-nodes-pinecone-assistant.pineconeAssistant",
  "typeVersion": 1.2
}
```

For complex filters, use `advancedMetadataFilter` (a JSON string) instead of `metadataFilter` — never both:
```json
"additionalFields": {
  "advancedMetadataFilter": "{\"department\": {\"$in\": [\"legal\", \"finance\"]}}"
}
```

#### Get Context Snippets
Use `resource: "contextSnippet", operation: "getContextSnippets"` to retrieve relevant text or image chunks directly — useful when you need raw retrieved context as workflow data rather than a chat reply.

```json
{
  "parameters": {
    "resource": "contextSnippet",
    "operation": "getContextSnippets",
    "assistantData": "{\"name\":\"[ASSISTANT_NAME]\",\"host\":\"https://[ASSISTANT_HOST]\"}",
    "query": "={{ $json.chatInput }}",
    "additionalFields": {
      "sourceTag": "n8n:n8n_nodes_pinecone_assistant:pinecone_n8n_skill",
      "includeMultimodalContext": true,
      "includeBinaryContent": true,
      "topK": 16,
      "snippetSize": 2048
    }
  },
  "type": "@pinecone-database/n8n-nodes-pinecone-assistant.pineconeAssistant",
  "typeVersion": 1.2
}
```

The same `metadataFilter` / `advancedMetadataFilter` options work on `getContextSnippets` to scope retrieval to files matching specific metadata. The `includeBinaryContent` flag only applies when `includeMultimodalContext` is `true`.

---

## Pinecone Vector Store Node — Best Practices and Workflow Generation

### Node package name
`@n8n/n8n-nodes-langchain.vectorStorePinecone`

### Prerequisites
- Create a Pinecone index in the Pinecone Console at https://app.pinecone.io/organizations/-/projects/-/indexes with the correct name and dimensions before running the workflow
- Set up a Pinecone credential in n8n with your API key
- Set up an OpenAI credential in n8n

### Workflow architecture
Two-phase workflow with two separate `vectorStorePinecone` node instances:

**Phase 1 — Ingestion** (run once or on a schedule):
```
Manual Trigger → Set file URLs → Split Out → HTTP Request (download)
  → Pinecone Vector Store (insert mode)
       ↑ Default Data Loader ← Recursive Character Text Splitter
       ↑ Embeddings OpenAI
```

**Phase 2 — Chat**:
```
Chat Trigger → AI Agent ← Pinecone Vector Store (retrieve-as-tool mode)
                               ↑ Embeddings OpenAI (same model as insert)
                        ← OpenAI Chat Model
```

### Key configuration rules
1. **Two node instances**: Use one `vectorStorePinecone` in `insert` mode for ingestion and a separate one in `retrieve-as-tool` mode for chat
2. **Embedding model consistency**: The SAME embedding model and dimensions MUST be used in both insert and retrieve-as-tool nodes — they share a single Embeddings OpenAI node via the `ai_embedding` connection
3. **Required companion nodes for the insert node**:
   - `@n8n/n8n-nodes-langchain.embeddingsOpenAi` — set dimensions to match your index (1536 for text-embedding-3-small)
   - `@n8n/n8n-nodes-langchain.textSplitterRecursiveCharacterTextSplitter` — connects to the data loader
   - `@n8n/n8n-nodes-langchain.documentDefaultDataLoader` — set `dataType: binary` and `textSplittingMode: custom`
4. **toolDescription**: Write a clear, specific description on the retrieve-as-tool node — the AI Agent uses this to decide when to query it
5. **topK**: Use 20 as the default; increase for broader recall, decrease to reduce token usage
6. **Metadata for citations**: In the Default Data Loader, add `external_file_url` as a metadata field set to `={{ $json.urls }}` so the AI Agent can cite sources
7. **Credential**: Use `pineconeApi` credential type

### Chunking guidance
- **3000 chars / 500 overlap**: Good default for long documents (articles, reports, documentation)
- **500–1000 chars / 100–200 overlap**: Better for Q&A-style retrieval or short, dense content
- Reference: https://www.pinecone.io/learn/chunking-strategies/

### Index setup instructions
When generating a workflow, always tell the user to:
1. Go to https://app.pinecone.io/organizations/-/projects/-/indexes and create an index
2. Set the name to match the `pineconeIndex` value in the workflow
3. Select the embedding model that matches the n8n Embeddings node (text-embedding-3-small → 1536 dimensions)

### Generating workflow JSON for the Vector Store path

Build the workflow to match what the user actually describes — their triggers, embedding model, chunking strategy, data sources, and structure. Ask about anything structurally significant they haven't mentioned. Only fall back to the defaults below when the user hasn't specified a value:
- Index name: `n8n-index` (use `n8n-index-1`, `n8n-index-2`, etc. for multiples; must match an existing Pinecone index)
- File URLs: sample Pinecone release notes PDFs
- LLM model: `gpt-5-mini`
- Embedding model: `text-embedding-3-small` (1536 dimensions)
- Chunk size: 3000 chars / 500 overlap
- System message / tool description: generic prompt about retrieving from the index with citations

The JSON below is a **reference configuration** showing correct parameter values, required fields, and connection types for each node. Use it as a guide for how to configure the nodes — not as a template to copy verbatim. Placeholders to substitute:
- `[INDEX_NAME]` — index name
- `[USER_FILE_URLS_ARRAY]` — JSON array of file URL strings, e.g. `["https://example.com/doc.pdf"]`
- `[USER_MODEL]` — LLM model name, e.g. `gpt-5-mini`
- `[USER_TOPIC]` — short description of the data, for the AI Agent system message
- `[USER_TOOL_DESCRIPTION]` — description of what data the vector store contains, for the tool node

```json
{
  "nodes": [
    {
      "parameters": {
        "mode": "insert",
        "pineconeIndex": {
          "__rl": true,
          "value": "[INDEX_NAME]",
          "mode": "list",
          "cachedResultName": "[INDEX_NAME]"
        },
        "options": {}
      },
      "type": "@n8n/n8n-nodes-langchain.vectorStorePinecone",
      "typeVersion": 1.3,
      "position": [224, 0],
      "id": "163c0a37-427c-4da7-a194-203ac216c88e",
      "name": "Pinecone Vector Store"
    },
    {
      "parameters": {
        "options": {"dimensions": 1536}
      },
      "type": "@n8n/n8n-nodes-langchain.embeddingsOpenAi",
      "typeVersion": 1.2,
      "position": [336, 608],
      "id": "a034bcb9-d813-4fd0-a68a-426c1f2b2aba",
      "name": "Embeddings OpenAI"
    },
    {
      "parameters": {"options": {}},
      "type": "@n8n/n8n-nodes-langchain.chatTrigger",
      "typeVersion": 1.3,
      "position": [-512, 896],
      "id": "56182cf7-2bda-4513-a2f9-18fb70c718ec",
      "name": "When chat message received",
      "webhookId": "30328376-a9e3-4f11-b1eb-2bbaadbea688"
    },
    {
      "parameters": {
        "options": {
          "systemMessage": "You are a helpful assistant. Only use the Pinecone Vector Store Tool to retrieve data about [USER_TOPIC]. Include the file name and file url in citations wherever referenced in output."
        }
      },
      "type": "@n8n/n8n-nodes-langchain.agent",
      "typeVersion": 2.2,
      "position": [-336, 896],
      "id": "36bb8361-edfd-47ff-aaf1-48f3c31fb1f7",
      "name": "AI Agent"
    },
    {
      "parameters": {
        "model": {
          "__rl": true,
          "value": "[USER_MODEL]",
          "mode": "list",
          "cachedResultName": "[USER_MODEL]"
        },
        "options": {}
      },
      "type": "@n8n/n8n-nodes-langchain.lmChatOpenAi",
      "typeVersion": 1.2,
      "position": [-336, 1200],
      "id": "22d00f25-44eb-40c1-8dae-b757e4b66690",
      "name": "OpenAI Chat Model"
    },
    {
      "parameters": {
        "mode": "retrieve-as-tool",
        "toolDescription": "[USER_TOOL_DESCRIPTION]",
        "pineconeIndex": {
          "__rl": true,
          "value": "[INDEX_NAME]",
          "mode": "list",
          "cachedResultName": "[INDEX_NAME]"
        },
        "topK": 20,
        "options": {}
      },
      "type": "@n8n/n8n-nodes-langchain.vectorStorePinecone",
      "typeVersion": 1.3,
      "position": [-16, 1104],
      "id": "15c599b7-93bb-44b7-b95c-190200de2a20",
      "name": "Pinecone Vector Store Tool"
    },
    {
      "parameters": {
        "content": "## 1. Process new files, embed, and upsert to Pinecone index",
        "height": 576,
        "width": 1744,
        "color": 7
      },
      "type": "n8n-nodes-base.stickyNote",
      "position": [-608, -80],
      "typeVersion": 1,
      "id": "18f22d77-fb10-4fa7-b942-2fafd7ca30c3",
      "name": "Sticky Note"
    },
    {
      "parameters": {
        "content": "## 2. Chat with your docs",
        "height": 640,
        "width": 1744,
        "color": 7
      },
      "type": "n8n-nodes-base.stickyNote",
      "position": [-608, 784],
      "typeVersion": 1,
      "id": "7b7be380-821c-4012-8f1a-1606527d2544",
      "name": "Sticky Note1"
    },
    {
      "parameters": {},
      "type": "n8n-nodes-base.manualTrigger",
      "typeVersion": 1,
      "position": [-512, 0],
      "id": "a0a3b917-765b-445e-9866-d3fc651ef6a8",
      "name": "When clicking 'Execute workflow'"
    },
    {
      "parameters": {
        "assignments": {
          "assignments": [
            {
              "id": "d0e724df-685f-4661-b2ec-3cdd3c2ba0f1",
              "name": "urls",
              "value": "[USER_FILE_URLS_ARRAY]",
              "type": "array"
            }
          ]
        },
        "options": {}
      },
      "type": "n8n-nodes-base.set",
      "typeVersion": 3.4,
      "position": [-352, 0],
      "id": "651439de-5525-4d0a-b055-1d722e81c0aa",
      "name": "Set file urls"
    },
    {
      "parameters": {"fieldToSplitOut": "urls", "options": {}},
      "type": "n8n-nodes-base.splitOut",
      "typeVersion": 1,
      "position": [-192, 0],
      "id": "8878265e-9e6f-4d9a-b533-53100205eb38",
      "name": "Split to list"
    },
    {
      "parameters": {
        "chunkSize": 3000,
        "chunkOverlap": 500,
        "options": {}
      },
      "type": "@n8n/n8n-nodes-langchain.textSplitterRecursiveCharacterTextSplitter",
      "typeVersion": 1,
      "position": [416, 352],
      "id": "347ba65b-9fad-4b92-a90f-6690df8e2a7e",
      "name": "Recursive Character Text Splitter"
    },
    {
      "parameters": {
        "url": "={{ $json.urls }}",
        "options": {"response": {"response": {"responseFormat": "file"}}}
      },
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [-32, 0],
      "id": "edf963af-18ee-4605-9b1e-49118c56b52d",
      "name": "Download file"
    },
    {
      "parameters": {
        "dataType": "binary",
        "textSplittingMode": "custom",
        "options": {
          "metadata": {
            "metadataValues": [
              {"name": "external_file_url", "value": "={{ $json.urls }}"}
            ]
          }
        }
      },
      "type": "@n8n/n8n-nodes-langchain.documentDefaultDataLoader",
      "typeVersion": 1.1,
      "position": [336, 192],
      "id": "e9b99301-3af1-4d19-ab78-3fd0e8946fd1",
      "name": "Default data loader"
    }
  ],
  "connections": {
    "Embeddings OpenAI": {
      "ai_embedding": [[
        {"node": "Pinecone Vector Store", "type": "ai_embedding", "index": 0},
        {"node": "Pinecone Vector Store Tool", "type": "ai_embedding", "index": 0}
      ]]
    },
    "When chat message received": {
      "main": [[{"node": "AI Agent", "type": "main", "index": 0}]]
    },
    "OpenAI Chat Model": {
      "ai_languageModel": [[{"node": "AI Agent", "type": "ai_languageModel", "index": 0}]]
    },
    "Pinecone Vector Store Tool": {
      "ai_tool": [[{"node": "AI Agent", "type": "ai_tool", "index": 0}]]
    },
    "When clicking 'Execute workflow'": {
      "main": [[{"node": "Set file urls", "type": "main", "index": 0}]]
    },
    "Set file urls": {
      "main": [[{"node": "Split to list", "type": "main", "index": 0}]]
    },
    "Split to list": {
      "main": [[{"node": "Download file", "type": "main", "index": 0}]]
    },
    "Recursive Character Text Splitter": {
      "ai_textSplitter": [[{"node": "Default data loader", "type": "ai_textSplitter", "index": 0}]]
    },
    "Download file": {
      "main": [[{"node": "Pinecone Vector Store", "type": "main", "index": 0}]]
    },
    "Default data loader": {
      "ai_document": [[{"node": "Pinecone Vector Store", "type": "ai_document", "index": 0}]]
    }
  },
  "pinData": {},
  "meta": {"templateCredsSetupCompleted": false}
}
```

---

## Debugging guidance

When a user reports a broken workflow, ask which node is failing and what error they see, then refer to these common issues:

| Error / Symptom | Cause | Fix |
|---|---|---|
| "Assistant not found" | `assistantData.name` doesn't match an existing assistant | Create the assistant in the Pinecone Console first, then match the name exactly |
| "Invalid credentials" | Pinecone API key not set or wrong credential on the node | Re-select the `pineconeApi` credential on each Pinecone node |
| "Dimension mismatch" | Embedding model dimensions don't match the index | Index and embeddings node must use the same dimensions (e.g., 1536 for text-embedding-3-small) |
| Tool never called by Agent | `toolDescription` is vague | Make the description specific: what data is in the store, what questions it can answer |
| No results returned | Ingestion didn't run, or topK too low | Run Phase 1 first; try increasing topK to 20+ |
| HTTP node calling Pinecone API | Wrong pattern | Replace with `@pinecone-database/n8n-nodes-pinecone-assistant.pineconeAssistant` or `@n8n/n8n-nodes-langchain.vectorStorePinecone` |

---

## Best practices review checklist

When reviewing an existing workflow:
1. **No HTTP nodes calling Pinecone endpoints** — replace any with the proper Pinecone node
2. **Vector Store**: same Embeddings node connected to both insert and retrieve-as-tool instances
3. **Assistant**: `assistantData` includes both `name` and `host`; `sourceTag` is present in `additionalFields`
4. **toolDescription** is specific and descriptive (not generic like "a vector store")
5. **Vector Store metadata**: `external_file_url` stored in the Default Data Loader metadata for source citations
6. **Assistant file metadata**: files uploaded with meaningful key-value metadata when filtering will be needed later
7. **Metadata filter**: `listFiles` and `getContextSnippets` use a metadata filter (not both filter fields at once) when scoping to a subset of files
8. **Multimodal upload**: `multimodalFile: true` is set on `uploadFile` when PDFs contain images or charts — this is required to index visual content and is NOT the default
9. **Multimodal retrieval**: `includeMultimodalContext: true` and `includeBinaryContent: true` on `getContextSnippets` when the workflow needs image chunks alongside text
10. **Chunk size** is appropriate for the content type (see chunking guidance above)
11. **Index exists** with correct dimensions before the workflow runs
