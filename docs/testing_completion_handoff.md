# Testing Completion Handoff

The active test target is the purge-first MVP:

1. Poll trusted sources.
2. Store content items.
3. Refresh entity/persona snapshots from content evidence.
4. Queue recent-content-biased Hub lead candidates.
5. Keep public pages public-safe.

## Current Test Posture

- Keep tests for source CRUD, polling, content item handling, entity/persona rebuilds, public pages, funding/idea public safety, LLM execution, and lead candidates.
- Removed workflow tests should not be reintroduced unless the product decision changes.
- Compatibility tables can appear in fixtures only when a test proves they no longer drive the public or admin MVP.

## Manual Smoke Path

- Open `/admin/`, poll sources, and rebuild stale snapshots.
- Open `/admin/leads`, use **Queue from recent content**, then review generated lead candidates.
- Open the public homepage, Explore, Latest, People, Organizations, Places, and Funding pages and confirm private admin intelligence is absent.

## Cleanup Notes

Database cleanup is intentionally separate from the product purge. See `docs/schema_cleanup_after_mvp_purge.md` for the migration gate.
