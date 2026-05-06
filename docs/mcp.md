# Synapse MCP server (read-only)

The Model Context Protocol server exposes retrieval helpers from [`app.identity.retrieval_facade`](../app/identity/retrieval_facade.py) so agents can read entity evidence without mutating the database.

Transport is **stdio** JSON-RPC using the official Python SDK (`mcp` package) and `FastMCP`, which matches what OpenAI documents for local MCP processes (command + stdio).

## Run

From the project root (with dependencies installed):

```bash
export PYTHONPATH=.
python -m app.mcp.server
```

Requires `pip install 'mcp>=1.0'` (see `requirements.txt`). Use the same `DATABASE_URL` / SQLite path as the web app.

## Synapse-native tools (always registered)

- `get_entity_persona_snapshot` — JSON snapshot of `PersonaSnapshot` for `person` / `organization` / `building`.
- `get_entity_evidence` — recent `ContentItem` rows for sources owned by the entity (optional `time_window_days`).
- `get_recent_rss_for_entity` — RSS-only items (newest first).
- `search_entity_corpus` — case-insensitive substring match on title and snippet.

## OpenAI ChatGPT Apps / company knowledge compatibility

OpenAI’s guide (“Building MCP servers for ChatGPT Apps and API integrations”) describes a **compatibility** contract for data-only apps: read-only tools named **`search`** and **`fetch`**, with JSON shapes suited to ChatGPT and deep research. That is **different** from generic MCP tool names; it is optional and **not** the only valid MCP setup.

This repo follows that contract when you enable:

| Variable | Purpose |
|----------|---------|
| `SYNAPSE_MCP_OPENAI_KNOWLEDGE_COMPAT=1` | Also register `search` and `fetch` (OpenAI shapes). |
| `SYNAPSE_MCP_ENTITY_TYPE` | `person`, `organization`, or `building` — corpus scope for `search` / `fetch`. |
| `SYNAPSE_MCP_ENTITY_ID` | Numeric id matching that entity. |

- **`search(query)`** returns a JSON string `{"results":[{"id","title","url"}, ...]}` (substring search over that entity’s ingested items).
- **`fetch(document_id)`** returns a JSON string with `id`, `title`, `text`, `url`, and `metadata` for a `ContentItem` id returned from `search`, with ownership checked against the same entity scope.

Typically you run **one MCP server process per ChatGPT app / connector** with a fixed `SYNAPSE_MCP_ENTITY_*` pair. For multi-entity or ad hoc queries, use the Synapse-native tools instead (they take `entity_type` and `entity_id` per call).

References:

- [Model Context Protocol — OpenAI API docs](https://developers.openai.com/api/docs/mcp) (includes company-knowledge compatibility)
- [Model Context Protocol specification](https://modelcontextprotocol.io/introduction)

### Confidence checklist

| Layer | Status |
|-------|--------|
| MCP wire protocol (stdio, tools listing, JSON results) | Implemented via official `mcp` SDK / `FastMCP`. |
| Arbitrary MCP clients (IDE, Codex-style stdio) | Compatible with Synapse-native tools. |
| OpenAI ChatGPT “search + fetch” product shape | Opt-in via `SYNAPSE_MCP_OPENAI_KNOWLEDGE_COMPAT` + entity env; matches the documented result shapes. |
| Hosted / Streamable HTTP MCP | Not implemented here; this server is stdio-only. Add a separate deploy if OpenAI or your host requires HTTP/SSE. |
