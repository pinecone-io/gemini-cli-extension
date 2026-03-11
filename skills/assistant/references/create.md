# Create Assistant

Create a new Pinecone Assistant with custom configuration.

## Arguments

- `--name` (required): Unique name for the assistant
- `--instructions` (optional): Behavior directive (tone, format, language)
- `--region` (optional): `us` or `eu` — default `us`
- `--timeout` (optional): Seconds to wait for ready status — default `30`

## Workflow

1. Parse arguments. If name is missing, prompt the user.
2. Ask the user about region preference — US or EU.
3. Ask if user wants custom instructions. Offer examples:
   - "Use professional technical tone and cite sources"
   - "Respond in Spanish with formal language"
4. Execute:
   ```bash
   uv run scripts/create.py \
     --name "assistant-name" \
     --instructions "instructions" \
     --region "us"
   ```
5. Show assistant name, status, and host URL.
6. Offer to run upload next.

## Naming Conventions

Suggest: `{purpose}-{type}` — e.g. `docs-qa`, `support-bot`, `api-helper`
Avoid: `test`, `assistant1`, `my-assistant`

## Post-Creation

- Save the assistant host URL shown in output (needed for MCP config)
- View and manage at: https://app.pinecone.io/organizations/-/projects/-/assistant/

## Troubleshooting

**Assistant name already exists** — list assistants and suggest a different name or delete the existing one.
**Timeout** — increase `--timeout 60`, check network connectivity.
**PINECONE_API_KEY not set** — export the variable or add to a `.env` file, then restart your IDE/agent session.
