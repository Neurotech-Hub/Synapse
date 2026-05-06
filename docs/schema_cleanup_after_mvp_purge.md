# Schema Cleanup After MVP Purge

This note tracks tables and columns retained only to keep existing development databases and migrations stable during the purge-first MVP reset.

## Compatibility-Only Storage

- `idea`
- `idea_suggestion`
- `match_run`
- `match_edge`
- `collaboration_hypothesis`
- public feed curation columns on `content_item`
- lead-report table names used behind the simplified Lead Candidate UI

These structures should not appear as active product concepts in routes, templates, current docs, or tests. They can remain until the replacement lead-candidate workflow is stable enough for a migration that either renames, migrates, or drops the old storage.

## Cleanup Gate

Do not remove storage until:

- the simplified operator loop has passing tests;
- existing rows have an explicit migration or archival decision;
- public/private gating tests still pass;
- cron-ready commands no longer depend on old workflow names.
