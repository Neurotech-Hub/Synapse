# Recent Progress and Remaining Work

## Purpose

This document summarizes the most recent Synapse implementation work and the major items still remaining.

## Recently Accomplished

### Live LLM Execution Foundation

- Added a generic provider boundary in `app/llm/providers.py`.
- Added a generic execution pipeline in `app/llm/execute.py`.
- Live prompt execution now routes through:
  - prompt registry
  - settings/cap checks
  - provider boundary
  - JSON parsing and validation
  - `LLMRun` logging
- Added test-only mock provider support.
- OpenAI is blocked by default unless explicitly allowed or escalation is enabled.
- Prompt-size caps and LLM synthesis enablement are enforced.
- Settings now shows prompt-run errors and validation problems.

### Admin Settings and LLM Safety

- `/admin/settings` exists.
- Settings shows:
  - feature flags
  - provider status
  - call caps
  - provider policy
  - recent prompt runs
- `LLMRun` exists and records prompt execution attempts.

### Funding Fetch and Synthesis Review Loop

- Added bounded funding source fetch/extract:
  - one URL only
  - HTTP(S) only
  - timeout and max-byte cap
  - private/localhost host guard
  - binary content rejection
  - readable text extraction
- Funding records now store fetch metadata and raw text hashes.
- Funding detail supports:
  - fetch source text
  - synthesize draft from fetched/raw text
  - apply synthesis draft fields
  - discard synthesis draft
  - use draft effort
- Synthesis output is review-gated and does not auto-publish.

### Idea Suggestions

- Added `IdeaSuggestion` model and migration.
- Added Idea suggestions from `PersonaSnapshot` through prompt execution.
- Added `/admin/ideas/suggestions`.
- Admin can:
  - generate suggestions from persona snapshots
  - accept suggestions as Ideas
  - reject suggestions
  - merge into duplicate candidate when detected
- Suggestions remain private until reviewed/accepted.

### Expanded Matching and Relationships

- Added manual relationship creation using `MatchEdge`.
- Added deterministic:
  - person-to-Idea matching
  - organization-to-Idea matching
  - funding-to-person matching
  - funding-to-organization matching through accepted Idea bridge edges
- Added target-centered Collaboration Hypothesis generation from accepted match sets.

### Admin Review Queue

- Added `/admin/review`.
- Review queue includes:
  - funding needing review
  - funding fetch/synthesis issues
  - pending Idea suggestions
  - pending match edges
  - draft/needs-review Collaboration Hypotheses
  - failed or validation-failed `LLMRun` rows

### Public Atlas MVP

- Added `/explore`.
- Added `/search`.
- Added homepage Idea/Funding spotlight section.
- Public pages still respect review/public visibility gates.
- Public pages still hide private scores, rationales, hypotheses, and outreach language.

## Latest Verification

Latest full verification after the recent implementation:

```text
Focused new workflow tests: 6 passed
Fresh migration chain: passed
Full suite: 185 passed, 1 skipped
Lints: no errors
```

## Still Remaining

### LLM Quality and Production Hardening

- Add real operator-facing controls for selecting provider/model per task.
- Add persistent editable settings if environment-backed settings are not enough.
- Add explicit OpenAI confirmation UI before paid calls.
- Add automatic JSON repair workflow if desired.
- Improve token/cost estimation and provider telemetry.
- Add per-prompt evaluation fixtures and regression examples.

### Funding Workflow

- Improve synthesis review UI with field-by-field apply/ignore controls.
- Add public-card regeneration as a distinct action.
- Add stronger source-text extraction for complex funder pages.
- Add better failed-fetch recovery and retry UX.
- Add optional URL refetch before resynthesis.
- Add high-value flag or review priority for strategic opportunities.

### Idea Workflow

- Add suggestions from `ContentItem`, not just `PersonaSnapshot`.
- Add richer duplicate detection and merge UI.
- Add manual relationship editor with friendlier entity pickers.
- Add Idea provenance panels showing source evidence and accepted suggestions.
- Add bulk review for generated suggestions.

### Matching

- Improve scoring quality beyond simple deterministic overlap.
- Add LLM rationale generation for selected top matches.
- Add Hub-to-target matching.
- Add place/building-to-Idea matching.
- Add staleness detection when Ideas, funding, personas, or tags change.
- Add better match detail pages.

### Collaboration Hypotheses

- Generate richer hypothesis text using the collaboration prompt.
- Include Hub capability context.
- Include recent public content evidence.
- Add edit/prioritize/dismiss/contact workflow.
- Add compatibility path with existing `LeadReport`.
- Add status history or notes for operator review.

### Public Discovery

- Polish `/explore` into a more complete atlas page.
- Improve `/search` ranking and snippets.
- Add public Places pages.
- Add related Ideas/Funding to public people and organization pages.
- Add related chips to Latest cards.
- Add request-support page.
- Add reusable public card/chip components.

### Admin UX

- Improve review queue grouping and filters.
- Add richer detail pages for match edges and hypotheses.
- Add bulk actions where review volume grows.
- Add clearer Settings documentation for what can trigger LLM calls.

## Recommended Next Steps

1. Improve funding synthesis review UI with field-by-field controls.
2. Add real funding public-card regeneration.
3. Add Idea suggestions from `ContentItem`.
4. Add match detail pages and LLM rationale generation for selected matches.
5. Add richer Collaboration Hypothesis generation using the prompt registry.
6. Add public people/org related Ideas/Funding sections.
7. Polish `/explore` and `/search`.

## Notes

- The app now has the core loop in MVP form:

```text
Evidence -> Fetch/Extract -> Synthesis -> Ideas -> Matches -> Hypotheses -> Public Discovery / Admin Review
```

- Several pieces are still thin MVPs, but they are now connected.
- Public/private safety remains enforced by review flags, visibility flags, and public-safe match-edge visibility.
