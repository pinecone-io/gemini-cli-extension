# Contextualization Guide for Incoming Skills

This repo is a **Gemini CLI extension**.
Skills here follow the Gemini CLI / Agent Skills standard.

## Skill Format Requirements

Each skill lives in `skills/<skill-name>/` and MUST have a `SKILL.md` at root.

### SKILL.md Structure

    ---
    name: <skill-name>
    description: <one-line description — this is the ONLY trigger mechanism>
    ---

    # Skill Title

    Instructions in Markdown...

### Critical Rules

1. **Frontmatter**: ONLY `name` and `description` fields. No other YAML keys.
   - `name` must be lowercase-kebab-case
   - `description` must be a single line. Include BOTH what the skill does AND
     when to use it. This is how Gemini decides to activate the skill.
   - Do NOT put "When to use" sections in the body — only the frontmatter
     description triggers activation.

2. **No `pinecone-` prefix** on directory names unless removing it would be
   ambiguous (e.g. keep `pinecone-docs` since just `docs` is too generic).

3. **File references**: Use relative paths from the skill root.
   - `scripts/` — executable code (Python, Bash, Node)
   - `references/` — additional docs loaded on demand
   - `assets/` — templates, icons, etc.

4. **Do NOT modify** `.py` files in `scripts/` directories.

5. **Keep SKILL.md under 500 lines**. Move detailed content to `references/`.

6. **Terminology mapping**:
   - "Claude Code" → "Gemini CLI"
   - "AGENTS.md" → "GEMINI.md"
   - "plugin" → "extension"
   - ".claude-plugin/" → not applicable here
   - Slash command references → describe as natural language actions

7. **Do not change**: Python scripts, Pinecone doc links, MCP tool names/params.
