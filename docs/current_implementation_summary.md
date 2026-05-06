# Current Implementation Summary

Synapse has been reset around a purge-first MVP.

## Active Product Surface

- Source ingestion for RSS feeds and HTML pages.
- Content items tied to sources.
- People, organizations, places, and persona snapshots.
- Public-safe discovery pages for recent content and listed entities.
- Hub lead candidates generated from recent content plus persona context.
- Admin operation around Sources, Content, Entities, Leads, Public Site, and Settings.

## Removed From Current Product

The old idea-suggestion triage, manual relationship administration, private hypothesis workflow, and separate report-management concept have been removed from active routes, templates, and current tests. Storage may remain temporarily for migration compatibility only; see `docs/schema_cleanup_after_mvp_purge.md`.

## Verification Focus

Current tests should cover the simple operator loop, public/private safety, source/content ingestion, persona rebuild behavior, and lead candidates. Historical sprint docs remain useful background, but they no longer define the MVP.
