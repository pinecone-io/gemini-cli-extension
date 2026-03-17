# Pinecone Gemini CLI Extension

The official Pinecone extension for the Gemini CLI. Manage vector indexes, perform semantic search, and build document Q&A assistants directly from your terminal using AI-powered Agent Skills and MCP tools.

## Quick Start

```bash
# 1. Install the extension
gemini extensions install https://github.com/pinecone-io/gemini-cli-extension

# 2. Set your API key (get one free at https://app.pinecone.io)
export PINECONE_API_KEY="your-api-key"

# 3. Restart Gemini CLI, then ask:
#    "Use the quickstart skill to help me get started with Pinecone"
```

> **Note:** If you hit API key errors, exit Gemini CLI, run `export PINECONE_API_KEY="your-key"` in your terminal, and start Gemini CLI again. The CLI only reads environment variables at launch.

## Installation

### 1. Prerequisites
- **Pinecone Account:** Create a free account at [app.pinecone.io](https://app.pinecone.io/?sessionType=signup).
- **Pinecone API Key:** Generate a key in the Pinecone console.
- **uv (Recommended):** To run the Python scripts bundled with the skills, [install uv](https://docs.astral.sh/uv/getting-started/installation/).
- **Pinecone CLI (Optional):** For advanced vector management, install the CLI:
  ```bash
  brew tap pinecone-io/tap
  brew install pinecone-io/tap/pinecone
  ```

### 2. Add the Extension
```bash
gemini extensions install https://github.com/pinecone-io/gemini-cli-extension
```

### 3. Configure the API Key
You must set your Pinecone API key in two places to unlock all features:

1. **MCP Configuration:** Add your key to the `PINECONE_API_KEY` setting in your Gemini CLI or MCP server configuration.
2. **Environment Variable:** Export the key in your terminal so the bundled skill scripts can access it:
   ```bash
   export PINECONE_API_KEY="your-api-key"
   ```

## Usage

### Agent Skills
This extension includes specialized **Agent Skills** that are automatically invoked based on your conversation. You don't need to memorize commands; just state your intent:

- *"Show me the Pinecone quickstart"*
- *"Create a document assistant from these files"*
- *"Search my 'products' index for 'green shoes'"*
- *"How do I manage namespaces with the Pinecone CLI?"*

**Note on Auto-Invocation:** If you find the agent isn't picking up a specific skill, you can explicitly ask for it by name: *"Use the `quickstart` skill to help me get started."*

### Available Skills
| Skill | Best Used For... |
|---|---|
| `quickstart` | Getting started with vector databases or document assistants. |
| `query` | Semantic text search on integrated indexes via MCP. |
| `assistant` | RAG-based document Q&A with citations. |
| `cli` | Learning and running `pc` terminal commands. |
| `mcp` | Reference for all available Pinecone MCP tools. |
| `pinecone-docs` | Looking up official documentation and API references. |
| `help` | Overview of all setup requirements and skills. |

### MCP Tools
The extension also provides direct access to Pinecone MCP tools for low-level operations like `list-indexes`, `describe-index`, and `search-records`.

## Troubleshooting

- **API Key Errors:** If a skill script fails, ensure you have exported `PINECONE_API_KEY` in your current terminal session.
- **Skill Activation:** If the agent is improvising instead of using a skill, try saying *"Activate the [skill-name] skill"*.
- **Documentation:** Use the `pinecone-docs` skill or visit [docs.pinecone.io](https://docs.pinecone.io) for help.

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](./CONTRIBUTING.md) for details on how to report issues or submit improvements.

## License

MIT
