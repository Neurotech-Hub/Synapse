# Recent Progress And Remaining Work

## Completed In The MVP Purge

- Added `docs/mvp_purge_decision.md` as the current product contract.
- Reframed Leads around recent-content-biased lead candidates.
- Removed legacy primary workflows from active admin navigation, templates, and tests.
- Removed old prompt/service entry points for suggestion, relationship, and hypothesis workflows.
- Added cron-ready commands for source polling, snapshot refresh, lead generation, and public latest checks.

## Still Open

- Run real LLM candidate generation against representative content and tune the prompts/data budgets.
- Decide whether compatibility tables should be migrated, archived, renamed, or dropped.
- Add production cron entries once the manual smoke path is stable.
- Keep public page polish focused on entity exploration and recent public signals.
