# Sprints 01-03 Review

## Purpose

This document reviews implementation status for:

- Sprint 01 — Funding Review and Trust Workflow
- Sprint 02 — ContentItem to Idea Suggestions
- Sprint 03 — Relationship Editor and Match Rationales

It highlights what was completed, what was intentionally skipped or kept thin, and why.

## Overall Status

All three sprints are complete for their stated MVP scope.

Latest verification after Sprint 03:

```text
Focused Sprint 03 tests: 28 passed
Fresh migration chain: passed
Full suite: 197 passed, 1 skipped
Lints: no errors
```

## Sprint 01 — Funding Review and Trust Workflow

### Completed

- Field-by-field funding synthesis review.
- Current value versus draft value display.
- Status indicators for:
  - new
  - changed
  - unchanged
  - missing
- Current/manual value indicator.
- Apply selected synthesized fields only.
- Ignored draft fields remain unchanged.
- Manual/current values are not overwritten silently.
- Public-card regeneration is a distinct action from full funding synthesis.
- Public-card output remains review-gated before public display.
- Draft effort can be applied separately.
- Deterministic effort rebuild still works.
- Fetch status/error metadata is visible on the Funding detail page.
- Fetch retry is available through the existing bounded fetch action.
- Fetch error can be cleared after review.
- Latest `LLMRun` status/errors appear on the Funding detail page.
- Public Funding pages do not expose unreviewed draft synthesis.
- CSV import still works.
- Public Funding Radar still works.

### Files / Areas Implemented

- `app/funding/synthesis.py`
- `app/funding/synthesis_review.py`
- `app/web/admin/routes.py`
- `templates/admin/funding/detail.html`
- `templates/admin/includes/help_funding_detail.html`
- `static/admin.css`
- `tests/test_funding_synthesis.py`
- `tests/test_funding_csv_import.py`
- `tests/test_public_funding_routes.py`

### Skipped or Kept Thin

| Item | Status | Why |
|---|---|---|
| Per-field manual override audit table | Skipped | The sprint only required preserving manual values and making current/manual values obvious. A full audit table would add schema and workflow complexity better suited to a later review/audit sprint. |
| Rich side-by-side public card design system | Kept thin | A clean admin preview card was added. A full visual design system would broaden the sprint beyond Funding review mechanics. |
| Perfect funding extraction quality | Skipped | The sprint goal was reviewability and trust, not perfect extraction across all funders. |
| Automatic public publishing from synthesis | Skipped intentionally | Public safety requires operator review before public pages use generated content. |
| Automatic JSON repair / fallback during funding synthesis | Skipped | JSON repair exists as prompt infrastructure, but automatic repair/escalation would add hidden model calls and cost risk. |

## Sprint 02 — ContentItem to Idea Suggestions

### Completed

- Admin can generate `IdeaSuggestion` records from one `ContentItem`.
- Suggestions are linked to:
  - `source_type = "content_item"`
  - `source_id = ContentItem.id`
  - `llm_run_id = LLMRun.id`
- ContentItem evidence packing includes:
  - content item ID
  - title
  - URL/link
  - source URL
  - source kind
  - published date
  - first seen date
  - snippet
- Added content-item idea extraction prompt.
- Suggestion review UI shows:
  - source type/id
  - evidence
  - LLM provider/model/status
  - confidence
  - duplicate candidate
  - duplicate reason/confidence
- Admin can accept suggestions as Ideas.
- Admin can reject suggestions.
- Admin can merge into duplicate candidate when detected.
- Duplicate detection includes:
  - normalized title
  - aliases
  - tag overlap
  - slug/title similarity
- Pending suggestions remain private and do not appear on public Ideas pages.
- PersonaSnapshot-based suggestions still work.

### Files / Areas Implemented

- `app/models.py`
- `app/ideas/suggestions.py`
- `app/llm/prompt_registry.py`
- `app/llm/validation.py`
- `app/web/admin/routes.py`
- `prompts/idea_extract_from_content_item.txt`
- `templates/admin/item_edit.html`
- `templates/admin/items_list.html`
- `templates/admin/ideas/suggestions.html`
- `migrations/versions/n1c2d3e4f5a6_idea_suggestion_duplicates.py`
- `tests/test_idea_suggestions.py`
- `tests/test_admin_contentitem_idea_suggestions.py`

### Skipped or Kept Thin

| Item | Status | Why |
|---|---|---|
| Batch ContentItem selection UI | Skipped | Sprint 02 allowed batch generation only if the UI already supported selection. It did not, and adding selection/bulk actions would broaden the sprint. |
| LLM-based duplicate judgment | Skipped intentionally | The directive specified deterministic duplicate detection minimums and said not to rely on LLM duplicate detection. |
| Rich merge editor | Kept thin | Merge into an existing duplicate candidate works. A richer field-by-field merge editor is larger UX work. |
| Public exposure of suggestions | Skipped intentionally | Suggestions must remain private until accepted, reviewed, and public. |
| Content body extraction beyond existing `ContentItem` fields | Kept thin | Evidence packing uses available title/link/source/snippet/date fields. A richer body extraction layer should be handled in an ingest/content sprint. |

## Sprint 03 — Relationship Editor and Match Rationales

### Completed

- Manual relationships use `MatchEdge`.
- Matching dashboard has friendlier dropdowns for common entities:
  - Idea
  - Funding
  - Person
  - Organization
- Manual relationships default to:
  - accepted
  - private unless explicitly public-safe
  - `features_json.manual = true`
- Match detail page exists at:

```text
/admin/matching/edges/<edge_id>
```

- Match detail page shows:
  - source entity
  - target entity
  - match type
  - status
  - visibility
  - score
  - confidence
  - MatchRun ID
  - LLMRun ID/status/provider when available
  - private rationale/note
  - public-safe summary candidate
  - evidence snippets
- Admin can:
  - accept from detail/dashboard
  - reject from detail/dashboard
  - archive from detail/dashboard
  - mark private
  - mark public-safe
  - edit private rationale/note
  - edit public-safe summary candidate
  - generate rationale for one selected match
- LLM rationale generation uses:
  - prompt registry
  - live LLM execution path
  - structured validation
  - `LLMRun`
- Invalid LLM output is logged as validation failure by the execution layer.
- Public pages still only use accepted edges with public-safe/public visibility and reviewed/public entities.
- Private rationale is not used by public templates.
- Existing deterministic matching still works.

### Files / Areas Implemented

- `app/matching/service.py`
- `app/web/admin/routes.py`
- `templates/admin/matching/dashboard.html`
- `templates/admin/matching/edge_detail.html`
- `tests/test_matching_expansion.py`
- `tests/test_admin_matching_routes.py`

### Skipped or Kept Thin

| Item | Status | Why |
|---|---|---|
| Searchable typeahead selectors | Kept thin | Dropdowns are friendlier than raw IDs and satisfy the “where practical” requirement. Full typeahead would require additional frontend behavior and is better for a later UX sprint. |
| New `EntityRelationship` table | Skipped intentionally | `MatchEdge` was flexible enough, and the directive said not to add a parallel relationship table unless necessary. |
| `created_by` schema field on `MatchEdge` | Skipped | Manual origin is stored in `features_json.manual = true`; adding a schema field was not necessary for MVP completion. |
| Batch LLM rationale generation | Skipped intentionally | Directive explicitly said selected-match action only and no batch rationale generation. |
| Major scoring overhaul | Skipped intentionally | Directive excluded major scoring overhaul. Existing deterministic scores remain. |
| Public display of generated public-safe summary text | Kept conservative | Public pages continue using accepted public-safe relationships without exposing private rationale. More nuanced public summary display can be handled after content review rules mature. |
| Full CRM-style workflow | Skipped intentionally | Explicitly out of scope. |

## Cross-Sprint Notes

### Public Safety

All three sprints preserve these rules:

- Public pages show only reviewed/public entities.
- Public relationship display requires accepted `MatchEdge` rows.
- Relationship visibility must be `public_safe` or `public`.
- Private rationale, match scores, LLM errors, draft synthesis, and pending suggestions are not exposed publicly.

### LLM Safety

All new live LLM paths use the generic execution infrastructure:

- prompt registry
- provider boundary
- settings/cap checks
- JSON validation
- `LLMRun` logging

Mock providers are used in tests, so the suite does not require live Ollama or OpenAI.

### UX Style

Admin additions reuse existing patterns:

- tables
- badges
- help popovers
- compact forms
- expandable detail sections
- existing button/link styles

No new visual system was introduced.

## Remaining Work After Sprints 1-3

The main remaining work is not from the sprint acceptance checklists, but from broader product polish:

- Better funding extraction quality for complex funder pages.
- Richer synthesis review UI for long fields and public-card previews.
- Batch ContentItem idea suggestion workflow.
- Searchable entity selectors in matching.
- Match detail pages with richer evidence rendering.
- LLM duplicate checks for ambiguous Ideas.
- Public display of curated relationship summaries, if desired.
- More complete admin review queue filters and bulk actions.
- Places/public atlas expansion.

## Final Assessment

Sprints 1-3 are complete for their stated MVP scopes.

The skipped items were either explicitly out of scope, intentionally deferred for public/private safety, or kept thin to avoid broadening the sprint into a larger UI/platform rewrite.
