# MVP Purge Decision

Synapse is now scoped around one automated loop:

1. Trusted sources produce content items.
2. Content items update people, organizations, and places through persona snapshots.
3. Recent content plus persona context generates Hub lead candidates.
4. Public pages expose only public-safe entities and recent signals.

The canonical MVP objects are `Person`, `Organization`, `Building`/place, `Source`, `ContentItem`, `PersonaSnapshot`, and Hub lead candidates backed by the existing lead storage until a cleanup migration replaces it.

## Removed From The MVP Product

The following workflows are no longer part of the active product:

- Idea suggestion triage.
- Manual relationship administration.
- Collaboration hypothesis review.
- Separate lead report management as a second concept beside lead candidates.
- Manual public feed curation as a required latest-content step.

Historical sprint docs may describe those workflows, but current implementation should not route daily operation through them. If related storage remains for migration compatibility, it is compatibility-only and must not drive navigation, current docs, templates, or tests.

## Operator Workflow

The admin should stay understandable from the sidebar:

- Sources: approve, assign, and poll inputs.
- Content: inspect what was ingested.
- Entities: maintain people, organizations, places, and snapshots.
- Leads: generate and review recent-content-biased Hub lead candidates.
- Public Site: manage public-safe resources.
- Settings: inspect provider health and active prompt/cap policies.
