# Synapse Testing Completion Handoff

## Purpose

This document summarizes what was implemented from `docs/planning_agent_direction.md`, what is still incomplete, and the manual steps needed to finish preparing the app for realistic testing.

It focuses on unfinished LLM/prompt integration, connectors, workflow gaps, and operator steps.

## Current Implementation Status

The app now has working foundations for:

- Funding opportunities, including model, migration, admin CRUD, CSV import, dry-run validation, duplicate detection, review/archive, and public/private visibility.
- Deterministic effort index classification with rationale, confidence, and signals.
- Manual Ideas, including model, migration, admin CRUD, review/archive, public Ideas pages, tags, aliases, summaries, and Hub capability fields.
- Matching foundations, including `MatchRun`, `MatchEdge`, and `CollaborationHypothesis` models.
- Deterministic funding-to-idea matching and admin review actions.
- Public Funding Radar and public Idea pages.
- Public-safe Idea/Funding cross-links from accepted `MatchEdge` rows with `public_safe` or `public` visibility.
- Prompt files and an offline prompt registry/validation layer.
- Admin help popovers for the new Funding, Ideas, and Matching pages.

Recent verification:

- Focused UI route tests after the latest UI polish: `14 passed`.
- Full suite before the latest UI-only polish: `164 passed, 1 skipped`.
- Full suite after public UX phase: `155 passed, 1 skipped`.
- Fresh migrations were verified through the new funding, idea, matching, and collaboration-hypothesis tables.

## Not Fully Implemented

### LLM and Prompt Integration

Prompt files now exist, and `app/llm/prompt_registry.py` plus `app/llm/validation.py` provide offline loading, rendering, fingerprinting, provider defaults, and structured JSON validation.

Still missing:

- No live LLM calls use the new prompt registry yet.
- Funding extraction prompt is not wired to an admin action.
- Funding public card prompt is not used to populate public summaries.
- Effort classification prompt is not used; only deterministic effort classification exists.
- Idea extraction from personas/content is not implemented.
- Idea public-page synthesis is not implemented.
- Matching prompts are not used for LLM scoring or rationale generation.
- Collaboration hypothesis prompt is not used for rich private synthesis.
- Outreach angle prompt exists but is not wired to any workflow.
- JSON repair prompt exists but is not invoked automatically.
- No `LLMRun` or equivalent prompt-call logging table exists yet.
- No token usage, latency, provider, model, or estimated cost logging exists for the new prompt layer.
- No admin settings page exists for prompt limits, provider selection, fallback behavior, OpenAI confirmation, or call caps.

Recommended next work:

- Add an `LLMRun` or `PromptRun` model before wiring live model calls.
- Route each new model call through `app/llm/prompt_registry.py`.
- Validate all structured outputs with `app/llm/validation.py`.
- Store prompt name, prompt version, provider, model, input fingerprint, output hash, status, latency, and errors.
- Keep all LLM-triggering admin actions explicit.

### Funding Connectors and Extraction

CSV import is implemented and should be the primary testing path.

Still missing:

- Admin URL fetch action for funding pages.
- Safe HTTP fetch helper for funding source pages.
- Readable HTML/text extraction for funding pages.
- Fetched text hash and fetch metadata population.
- Refetch/rebuild workflow.
- Fetch error display on funding detail pages.
- Synthesis from fetched text into structured funding fields.
- Automatic public summary generation from source text.

Recommended next work:

- Add `app/funding/fetch.py` and `app/funding/extract.py`.
- Add admin action on Funding detail: `Fetch source text`.
- Store final URL, content type, status code, fetch error, fetched timestamp, raw text, and raw text hash.
- Keep fetch bounded to one URL with timeouts and no recursive crawling.

### Idea Workflows

Manual Ideas are implemented.

Still missing:

- Suggest Ideas from a person, organization, building, or region persona.
- Suggest Ideas from content items.
- Review screen for LLM-suggested Ideas.
- Accept/reject/merge flow for generated candidates.
- Duplicate detection and merge workflow.
- Manual relationship editor for linking Ideas to people, organizations, places, funding, or content.
- Public Idea pages do not yet show related people, organizations, places, or latest signals.

Recommended next work:

- Add a candidate Idea generation service that uses existing `PersonaSnapshot` rows.
- Store generated candidates as draft/unreviewed Ideas or a separate suggestion object.
- Add duplicate detection before creating new Ideas.
- Add a lightweight manual relationship model or extend matching workflows to cover Idea-to-entity links.

### Matching and Lead Workflows

The matching foundation exists, but it is intentionally narrow.

Implemented:

- Funding-to-Idea deterministic candidate generation.
- Private match edges.
- Admin accept/reject/archive controls.
- Public-safe visibility gate for public cross-links.
- Simple private Collaboration Hypothesis creation from one funding-to-idea edge.

Still missing:

- Person-to-Idea matching.
- Organization-to-Idea matching.
- Building/region-to-Idea matching.
- Funding-to-person matching.
- Funding-to-organization matching.
- Hub-to-target matching.
- LLM scoring/rationale for matches.
- Batch match queue/job handling beyond synchronous admin action.
- Staleness handling when funding, Ideas, personas, or tags change.
- Rich Collaboration Hypothesis generation from target entity plus multiple matches.
- LeadReport-to-CollaborationHypothesis compatibility workflow.
- Admin workflow for dismissing, prioritizing, editing, or converting hypotheses into actions.

Recommended next work:

- Keep deterministic candidate generation before any LLM scoring.
- Add match generation by entity type in small slices.
- Add target-centered hypothesis generation only after accepted match sets are available.
- Preserve existing `LeadReport` behavior until a deliberate migration path is implemented.

### Public UX and Discovery

Implemented:

- Public Ideas index/detail.
- Public Funding Radar index/detail.
- Public-safe Idea/Funding related cards.
- Feature flags for public Ideas and public Funding.

Still missing:

- `/explore` page.
- `/search` page.
- Public Places pages.
- Homepage refresh with Idea spotlights and Funding Radar preview.
- Related Ideas/Funding on public people and organization pages.
- Related entity chips/components shared across public pages.
- Request-support page.
- Public latest cards do not yet show related Ideas/Funding chips.
- Public filtering is still minimal.

Recommended next work:

- Add `/explore` before adding complex graph visualization.
- Add simple grouped search over public people, organizations, Ideas, Funding, and latest content.
- Add related cards to public person/org pages only when relationships are accepted and public-safe.

### Admin UX and Settings

Implemented:

- Admin Funding, Ideas, and Matching navigation.
- Help popovers for new admin workflows.
- Tables and detail pages for the new objects.

Still missing:

- Admin Settings area for feature flags and provider controls.
- UI for prompt character limits, batch size, match candidate limits, retry caps, and OpenAI confirmation.
- Admin visibility into prompt/LLM run history.
- Admin controls for public-safe match visibility beyond simple match-edge actions.
- Bulk review queues for imported funding, generated Ideas, matches, or hypotheses.

Recommended next work:

- Add a lightweight Settings page before wiring more LLM calls.
- Start with environment-backed settings displayed read-only or editable with safe defaults.
- Include provider status, caps, feature flags, and OpenAI escalation policy.

## Manual Steps To Complete Local Testing

### 1. Create or Activate a Python Environment

The system Python may be externally managed. Use a virtual environment.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

### 2. Configure Required Environment

At minimum:

```bash
export ADMIN_PASSWORD="test-pass"
export FLASK_APP=wsgi
```

Optional feature flags:

```bash
export SYNAPSE_PUBLIC_IDEAS_ENABLED=1
export SYNAPSE_PUBLIC_FUNDING_ENABLED=1
export SYNAPSE_MATCHING_ENABLED=1
```

Optional local LLM:

```bash
export OLLAMA_HOST="http://127.0.0.1:11434"
export OLLAMA_MODEL="llama3.2"
```

Optional OpenAI:

```bash
export OPENAI_API_KEY="..."
```

Do not enable automatic OpenAI escalation until admin controls/logging are added.

### 3. Apply Database Migrations

Use a local development database.

```bash
flask --app wsgi db upgrade
```

Expected new tables include:

- `funding_opportunity`
- `idea`
- `match_run`
- `match_edge`
- `collaboration_hypothesis`

### 4. Run Tests

Fast full gate:

```bash
pytest
```

Useful focused gates:

```bash
pytest tests/test_funding_model.py tests/test_funding_csv_import.py
pytest tests/test_effort_index.py
pytest tests/test_idea_model.py tests/test_admin_ideas_routes.py
pytest tests/test_match_models.py tests/test_matching_scoring.py tests/test_admin_matching_routes.py
pytest tests/test_public_funding_routes.py tests/test_public_ideas_routes.py
pytest tests/test_prompt_registry.py tests/test_prompt_validation.py
```

### 5. Start the App

```bash
flask --app wsgi run --debug
```

Then open:

```text
http://127.0.0.1:5000/
http://127.0.0.1:5000/admin/
```

### 6. Import Funding Test Data

Use the admin UI:

```text
/admin/funding/import
```

Upload:

```text
data/funding_opportunities_sample.csv
```

Recommended workflow:

1. Upload with `Commit valid rows` unchecked.
2. Review row-level errors and duplicate warnings.
3. Upload again with `Commit valid rows` checked.
4. Review imported funding records.
5. Mark selected records reviewed.
6. Ensure selected records have `public` visibility.

Note: the sample contains a duplicate URL row intentionally. That should remain useful for testing duplicate detection.

### 7. Create or Review Ideas

Use:

```text
/admin/ideas
```

Create a few public Ideas with overlapping tags, for example:

- Automated home-cage behavioral monitoring
- Embedded neuroscience data logging
- Closed-loop behavioral systems

For each public Idea:

1. Set status to `public`.
2. Check `Public`.
3. Check `Reviewed`.
4. Add tags that overlap with funding topic or method tags.

### 8. Generate Matches

Use:

```text
/admin/matching
```

Generate matches by selecting a Funding record or Idea.

Then:

1. Review generated `MatchEdge` rows.
2. Accept useful matches.
3. Change visibility to `public_safe` if they are appropriate for public pages.
4. Optionally create a private Collaboration Hypothesis from an accepted edge.

Only accepted `public_safe` or `public` edges can appear on public Idea/Funding pages.

### 9. Verify Public Pages

Open:

```text
/ideas/
/funding/
```

Expected behavior:

- Draft/private/unreviewed Ideas do not appear.
- Draft/private/unreviewed Funding records do not appear.
- Public Funding cards show effort, sponsor, deadline/amount if present, tags, and source link.
- Public Idea pages show related Funding only from accepted public-safe match edges.
- Public pages do not show match scores, private rationales, private summaries, or collaboration hypotheses.

## Suggested Next Implementation Order

1. Add funding URL fetch/extract.
2. Add `LLMRun`/prompt-call logging.
3. Add admin Settings for provider controls and call caps.
4. Wire funding extraction through prompt registry and JSON validation.
5. Wire funding public-card synthesis.
6. Add Idea extraction from persona snapshots.
7. Add duplicate detection/merge for Ideas.
8. Expand matching beyond funding-to-idea.
9. Add rich target-centered Collaboration Hypothesis generation.
10. Add `/explore`, `/search`, homepage refresh, and public related cards across people/org/place pages.

## Testing Risk Notes

- The current matching workflow is deterministic and narrow. It is useful for exercising public-safe relationships but not a full lead-generation engine.
- Public pages depend on review flags and visibility flags. Missing records on public pages usually means the row is not reviewed, not public, archived, private, or missing a public-safe accepted match.
- Prompt files exist, but prompt execution is not wired. Do not expect LLM-generated funding summaries, Ideas, match rationales, or collaboration hypotheses yet.
- OpenAI/Ollama status shown in existing admin sidebar is not the same as integrated prompt execution for the new features.
- The current admin UI is suitable for manual testing but not yet optimized for high-volume review queues.
