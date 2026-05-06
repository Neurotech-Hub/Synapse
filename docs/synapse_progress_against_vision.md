# Synapse Progress Against Vision

The working vision is now simpler: Synapse should use AI to keep a lightweight research atlas and generate Hub lead candidates from recent content without forcing operators to manage a graph.

## What Exists

- Ingestion for sources and content items.
- Entity records for people, organizations, and places.
- Persona snapshots built from owned source evidence.
- Public discovery pages for approved public-safe content.
- A Leads workflow for recent-content-biased Hub candidates.

## What Was Purged

- Dedicated idea-suggestion triage.
- Manual relationship administration.
- Private hypothesis review as a separate queue.
- Separate report-management language in the operator UI.
- Manual feed curation as a required public Latest step.

## Next Direction

Make the loop reliable enough for cron:

```text
poll sources -> refresh snapshots -> queue lead candidates -> review leads -> public-safe discovery
```

The barrier to entry should stay low: add sources, trust content, let AI synthesize candidates, and publish only public-safe discovery material.
