# Synapse Current Implementation Summary

## Purpose

This document summarizes what has been implemented so far and what remains open after the funding, ideas, matching, public UX, prompt, settings, logging, and funding fetch foundation work.

## Implemented

### Funding Foundation

- `FundingOpportunity` model exists in `app/models.py`.
- Funding migrations exist, including follow-up migrations for effort fields and fetch metadata.
- Admin Funding pages exist:
  - list
  - detail
  - create/edit
  - archive
  - CSV import
  - review
  - effort rebuild
  - source-text fetch
- CSV import supports:
  - dry-run validation
  - row-level errors
  - duplicate detection by `external_id` and normalized source URL
  - optional update-on-duplicate
- Synthetic CSV fixtures exist under `tests/fixtures/`.
- Public Funding Radar exists:
  - `/funding/`
  - `/funding/<slug>`
  - status and effort filters
  - public-safe related Ideas
  - source link and caveat copy

### Funding Fetch and Extraction

- Bounded funding source fetching exists in `app/funding/fetch.py`.
- Readable text extraction exists in `app/funding/extract.py`.
- Fetch behavior is intentionally conservative:
  - one URL only
  - HTTP(S) only
  - timeout required
  - max response byte cap
  - binary content rejection
  - private/localhost host guard unless explicitly allowed
- Funding records can store:
  - final URL
  - HTTP status
  - content type
  - fetch error
  - fetched timestamp
  - raw extracted text
  - raw text hash
  - source text character count

### Effort Index

- Deterministic effort classifier exists in `app/funding/effort.py`.
- Funding records store:
  - effort label
  - score
  - confidence
  - rationale
  - signals
  - effort review timestamp
- Admin can manually override effort.
- Admin can rebuild effort deterministically.

### Ideas

- `Idea` model exists in `app/models.py`.
- Admin Ideas pages exist:
  - list
  - detail
  - create/edit
  - review
  - archive
- Public Ideas pages exist:
  - `/ideas/`
  - `/ideas/<slug>`
- Public Idea pages can show related public Funding when accepted public-safe match edges exist.

### Matching and Collaboration Hypotheses

- Matching models exist:
  - `MatchRun`
  - `MatchEdge`
  - `CollaborationHypothesis`
- Deterministic funding-to-Idea matching exists in `app/matching/service.py`.
- Admin Matching dashboard exists.
- Admin can:
  - generate funding-to-Idea matches
  - generate Idea-to-funding matches
  - accept/reject/archive match edges
  - mark edges private or public-safe
  - create a simple private Collaboration Hypothesis from one funding-to-Idea match
- Existing `LeadReport` behavior remains intact.

### Public UX

- Public navigation includes Ideas and Funding.
- Public Funding Radar and public Ideas use the current site aesthetic.
- Public pages only show reviewed/public entities.
- Public related Funding/Ideas only use accepted match edges with `public_safe` or `public` visibility.
- Private match scores, private rationales, collaboration hypotheses, and outreach language are not exposed publicly.

### Prompt Infrastructure

- Prompt files exist for:
  - funding extraction
  - effort classification
  - funding public card
  - idea extraction
  - idea public synthesis
  - matching
  - Hub-to-target matching
  - collaboration hypotheses
  - outreach angles
  - lead score explanations
  - public entity/place/atlas summaries
  - JSON repair
- Prompt registry exists in `app/llm/prompt_registry.py`.
- Structured output validation exists in `app/llm/validation.py`.
- Prompt rendering, versioning, provider defaults, and input fingerprints are implemented.

### LLM Safety and Logging Foundation

- Admin Settings page exists at `/admin/settings`.
- Settings page shows:
  - feature flags
  - provider status
  - call caps
  - provider policy
  - recent prompt runs
- `LLMRun` model exists in `app/models.py`.
- `app/llm/run.py` provides offline logging helpers:
  - create run
  - complete run
  - fail run
  - prompt hash
  - output hash
  - estimated token counts
- No live LLM feature is wired yet.

### Admin UX

- Funding, Ideas, Matching, and Settings are in admin navigation.
- New admin pages use help popovers for explanatory information.
- Detail pages keep main content lighter with expandable sections where helpful.

## Verification

Recent verification after the Next Sprint Foundation work:

```text
Focused foundation tests: 14 passed
Fresh migration chain: passed
Full test suite: 173 passed, 1 skipped
Lints: no errors
```

## Still Open

### Live LLM Execution

Prompt files and logging infrastructure exist, but live model calls are not wired.

Still needed:

- Provider wrapper that actually calls Ollama/OpenAI through the prompt registry.
- Settings/cap checks before every live call.
- JSON validation and optional repair after every live call.
- `LLMRun` records for all live calls.
- Admin visibility for validation errors and failed prompt outputs.

### Funding Synthesis

Fetch/extract now exists, but synthesis is not implemented.

Still needed:

- Admin action: synthesize funding fields from fetched text.
- Admin action: regenerate public funding card.
- Admin action: reclassify effort from fetched/synthesized text.
- Safe merge behavior so synthesis does not overwrite manual review fields without confirmation.
- Review UI for synthesized fields.

### Idea Suggestions

Ideas are manual only.

Still needed:

- Suggest Ideas from `PersonaSnapshot`.
- Suggest Ideas from `ContentItem`.
- Review screen for generated Idea candidates.
- Accept/reject/merge flow.
- Duplicate detection.
- Relationship linking from Ideas to people, organizations, buildings/regions, content, and funding.

### Matching Expansion

Only deterministic funding-to-Idea matching exists.

Still needed:

- person-to-Idea matching
- organization-to-Idea matching
- building/region-to-Idea matching
- funding-to-person matching
- funding-to-organization matching
- Hub-to-target matching
- LLM match rationale generation
- match staleness when source objects change
- richer match review queues

### Collaboration Hypotheses

Only simple hypothesis creation from one funding-to-Idea match exists.

Still needed:

- target-centered hypothesis generation
- synthesis from multiple accepted matches
- Hub capability context
- funding and effort context
- recommended action generation
- edit/dismiss/prioritize/contact workflow
- LeadReport-to-CollaborationHypothesis compatibility path

### Public Discovery

Public Ideas and Funding exist, but the full atlas layer is not complete.

Still needed:

- `/explore`
- `/search`
- public Places pages
- homepage refresh with Idea and Funding sections
- related Ideas/Funding on public people and organization pages
- related chips on Latest cards
- request-support page
- reusable public card/chip components

### Admin Review Queues

Objects exist across Funding, Ideas, Matching, Hypotheses, and LLM runs, but there is not yet a central review queue.

Still needed:

- `/admin/review`
- imported Funding needing review
- funding fetch/synthesis failures
- generated Idea suggestions
- pending match edges
- draft Collaboration Hypotheses
- public-safe visibility candidates
- failed `LLMRun` rows

### Settings Persistence

Settings are currently environment-backed/read-only.

Still needed if operator control from the UI is required:

- persistent settings model or singleton table
- editable caps and feature flags
- explicit OpenAI confirmation policy
- per-task provider defaults
- audit trail for settings changes

## Recommended Next Implementation Order

1. Wire funding synthesis through `app/llm/prompt_registry.py`, `app/llm/validation.py`, and `LLMRun`.
2. Add review UI for synthesized funding fields.
3. Add effort regeneration from fetched/synthesized text.
4. Add funding public-card synthesis.
5. Add Idea suggestions from personas/content.
6. Add duplicate detection and merge workflow for Ideas.
7. Add manual/public-safe relationship editing.
8. Expand deterministic matching to people and organizations.
9. Add LLM rationale generation for top reviewed matches.
10. Add richer Collaboration Hypothesis generation.
11. Add Admin Review queues.
12. Add `/explore`, `/search`, homepage refresh, and richer public cross-links.

## Manual Testing Path

Use this flow for end-to-end manual testing today:

1. Apply migrations:

```bash
flask --app wsgi db upgrade
```

2. Start the app:

```bash
flask --app wsgi run --debug
```

3. Open admin:

```text
/admin/
```

4. Check Settings:

```text
/admin/settings
```

5. Import funding CSV:

```text
/admin/funding/import
```

Use:

```text
data/funding_opportunities_sample.csv
```

6. Review funding records:

```text
/admin/funding/
```

7. For a funding record:

- review/edit metadata
- fetch source text if the URL is reachable
- rebuild effort if useful
- mark reviewed
- set public visibility

8. Create or review Ideas:

```text
/admin/ideas/
```

9. Generate matches:

```text
/admin/matching/
```

10. Accept useful matches and mark selected relationships public-safe.

11. Verify public pages:

```text
/ideas/
/funding/
```

## Notes and Constraints

- CSV import remains the most reliable funding ingestion path.
- Funding fetch is bounded but does not guarantee clean extraction from every funder page.
- No LLM synthesis happens automatically.
- OpenAI escalation is disabled by default.
- Public pages intentionally hide private notes, scores, rationales, and hypotheses.
- Existing persona, ingest, public latest, and LeadReport flows should remain functional.
