"""Read-only MCP server (stdio) exposing Synapse entity corpus tools.

Run (with app on PYTHONPATH):

    python -m app.mcp.server

Requires: ``pip install 'mcp>=1.0'``

OpenAI ChatGPT Apps / company-knowledge shape (``search`` + ``fetch`` tools) is available when
``SYNAPSE_MCP_OPENAI_KNOWLEDGE_COMPAT=1`` and entity scope env vars are set — see ``docs/mcp.md``.
"""

from __future__ import annotations

import os
import sys


def _truthy_env(key: str) -> bool:
    v = (os.environ.get(key) or "").strip().lower()
    return v in ("1", "true", "yes", "on")


def _entity_scope_from_env() -> tuple[str, int] | None:
    """Optional (entity_type, entity_id) for OpenAI knowledge tools and scoped operation."""

    et = (os.environ.get("SYNAPSE_MCP_ENTITY_TYPE") or "").strip().lower()
    eid_raw = (os.environ.get("SYNAPSE_MCP_ENTITY_ID") or "").strip()
    if et not in ("person", "organization", "building") or not eid_raw.isdigit():
        return None
    return et, int(eid_raw)


def _stdio_utf8() -> None:
    """Avoid Windows stdout encoding issues for JSON-RPC."""

    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stdin.reconfigure(encoding="utf-8")
        except Exception:
            pass


def main() -> None:
    _stdio_utf8()

    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as e:
        raise SystemExit(
            "MCP SDK not installed. Install with: pip install 'mcp>=1.0'\n" f"Original error: {e}"
        ) from e

    from app import create_app
    from app.identity import retrieval_facade as rf

    _instructions = (
        "Synapse read-only corpus: entity-scoped ingest evidence (RSS/HTML). "
        "For OpenAI ChatGPT Apps-style search+fetch, set SYNAPSE_MCP_OPENAI_KNOWLEDGE_COMPAT=1, "
        "SYNAPSE_MCP_ENTITY_TYPE (person|organization|building), and SYNAPSE_MCP_ENTITY_ID. "
        "Configure DATABASE_URL / Flask the same as the web app."
    )
    mcp = FastMCP("synapse", instructions=_instructions)

    @mcp.tool()
    def get_entity_persona_snapshot(entity_type: str, entity_id: int) -> str:
        """Load stored PersonaSnapshot fields for a person, organization, or building."""

        app = create_app()
        with app.app_context():
            return rf.json_dumps(rf.get_entity_persona_snapshot(entity_type, int(entity_id)))

    @mcp.tool()
    def get_entity_evidence(
        entity_type: str, entity_id: int, time_window_days: int | None = None, limit: int = 40
    ) -> str:
        """Recent ingested content items and source metadata for an entity (optionally time-filtered)."""

        app = create_app()
        with app.app_context():
            tw = None if time_window_days is None or int(time_window_days) <= 0 else int(time_window_days)
            return rf.json_dumps(rf.get_entity_evidence(entity_type, int(entity_id), time_window_days=tw, limit=int(limit)))

    @mcp.tool()
    def get_recent_rss_for_entity(entity_type: str, entity_id: int, limit: int = 30) -> str:
        """RSS-sourced content items only (newest first)."""

        app = create_app()
        with app.app_context():
            return rf.json_dumps(rf.get_recent_rss_for_entity(entity_type, int(entity_id), limit=int(limit)))

    @mcp.tool()
    def search_entity_corpus(entity_type: str, entity_id: int, query: str, limit: int = 25) -> str:
        """Substring search across titles and snippets for an entity's owned corpus."""

        app = create_app()
        with app.app_context():
            return rf.json_dumps(rf.search_entity_corpus(entity_type, int(entity_id), query, limit=int(limit)))

    if _truthy_env("SYNAPSE_MCP_OPENAI_KNOWLEDGE_COMPAT"):

        @mcp.tool()
        def search(query: str) -> str:
            """OpenAI company-knowledge: return JSON ``{\"results\":[{\"id\",\"title\",\"url\"}]}`` (scoped env).

            Requires ``SYNAPSE_MCP_ENTITY_TYPE`` and ``SYNAPSE_MCP_ENTITY_ID`` at server startup.
            See https://developers.openai.com/api/docs/mcp#company-knowledge-compatibility
            """

            scope = _entity_scope_from_env()
            if scope is None:
                return '{"results":[]}'
            app = create_app()
            with app.app_context():
                return rf.openai_company_knowledge_search_text(
                    query or "",
                    entity_type=scope[0],
                    entity_id=scope[1],
                )

        @mcp.tool()
        def fetch(document_id: str) -> str:
            """OpenAI company-knowledge: full document by id from ``search`` results.

            ``document_id`` is the ContentItem id string returned in search results.
            """

            scope = _entity_scope_from_env()
            if scope is None:
                return '{"id":"","title":"","text":"","url":"","metadata":{"error":"missing_entity_scope"}}'
            app = create_app()
            with app.app_context():
                return rf.openai_company_knowledge_fetch_text(
                    document_id or "",
                    entity_type=scope[0],
                    entity_id=scope[1],
                )

    mcp.run()


if __name__ == "__main__":
    main()
