# Sprint 01 — Funding Review and Trust Workflow

## Primary References

Read these first, but implement only the scope in this sprint:

```text
docs/synapse_progress_against_vision.md
docs/recent_progress_and_remaining.md
docs/funding_model.md
docs/effort_index.md
docs/prompt_specs.md
```

## Sprint Goal

Improve the Funding workflow so an operator can confidently turn imported or fetched funding opportunities into reviewed, public-safe records.

The system already has:

- `FundingOpportunity`
- CSV import
- bounded source fetch/extract
- funding synthesis draft workflow
- deterministic effort index
- public Funding Radar
- LLM execution, prompt registry, validation, and `LLMRun`

This sprint should make the funding review loop more trustworthy and usable.

## In Scope

### 1. Field-by-field synthesis review

Add a review interface that compares:

```text
current FundingOpportunity value
synthesized draft value
```

For each supported field, allow the operator to:

```text
apply synthesized value
ignore synthesized value
keep current value
```

Fields should include, where present:

```text
title
sponsor_name
summary_public
summary_private
eligibility_summary
amount_text
deadline_text
deadline_date
topic_tags_json
method_tags_json
possible_hub_relevance
effort_index
effort_rationale
```

### 2. Preserve manual overrides

Manual edits must not be overwritten silently.

If a field already has a reviewed/manual value, the UI should make that obvious.

Recommended UI treatment:

```text
Current value
Draft value
Apply draft
Keep current
```

### 3. Highlight changed fields

The review UI should distinguish:

```text
unchanged fields
newly filled fields
changed fields
missing draft fields
```

Simple badges are enough.

Examples:

```text
New
Changed
Unchanged
Missing
Manual value present
```

### 4. Public-card regeneration action

Add a distinct action for regenerating public-facing funding card text.

This should not be the same action as full funding extraction.

Recommended admin actions:

```text
Synthesize funding fields
Regenerate public card
Apply selected draft fields
Discard draft
```

The public-card regeneration should update a draft/reviewable value first, not immediately overwrite a reviewed public summary unless the operator confirms.

### 5. Effort update from synthesis

If synthesis returns effort information, allow the operator to apply it separately.

Recommended controls:

```text
Use draft effort
Keep current effort
Rebuild deterministic effort
Manual override
```

### 6. Failed fetch / retry UX

Improve the Funding detail page so failed fetches and synthesis failures are visible and recoverable.

Show:

```text
last fetch timestamp
final URL
HTTP status
content type
source text char count
raw text hash
fetch error
latest synthesis status
latest LLMRun status/error
```

Add or improve actions:

```text
Fetch source text again
Synthesize from existing text
Clear fetch error if resolved
View latest LLMRun
```

## Out of Scope

Do not implement these in this sprint:

```text
Idea suggestions from ContentItem
manual relationship editor
expanded match detail pages
LLM match rationale generation
Hub-to-target matching
public atlas redesign
public Places pages
persistent editable settings
LeadReport migration
email/outreach automation
```

## Recommended Architecture

### Reuse existing structures

Prefer extending existing Funding admin routes/templates/services.

Likely areas:

```text
app/funding/
app/web/admin/routes.py
app/web/admin/templates/
app/llm/
tests/
```

Actual file names may differ. Inspect the repo before editing.

### Suggested service boundary

If not already present, create a small service for applying drafts:

```text
app/funding/synthesis_review.py
```

Responsibilities:

```text
compute field diffs
apply selected fields
preserve manual values
normalize tags
validate date fields
record review/apply timestamps
```

### Suggested helper functions

```text
get_funding_synthesis_diff(funding) -> list[FieldDiff]
apply_funding_synthesis_fields(funding, selected_fields) -> ApplyResult
regenerate_funding_public_card(funding, provider_policy) -> DraftResult
```

### FieldDiff shape

Use a simple internal structure:

```json
{
  "field": "summary_public",
  "label": "Public summary",
  "current_value": "...",
  "draft_value": "...",
  "status": "new|changed|unchanged|missing",
  "is_manual": true,
  "can_apply": true
}
```

This does not need to be a database model unless the current synthesis storage requires it.

## UI/UX Requirements

Maintain the existing admin aesthetic.

Use existing:

```text
cards
tables
badges
help popovers
button styles
expandable sections
```

Do not introduce a new visual system.

Funding detail page should have clear sections:

```text
1. Core funding metadata
2. Source fetch status
3. Synthesis draft review
4. Effort index
5. Public visibility
6. Related Ideas/Funding matches if already present
```

## Public-Safety Requirements

No unreviewed synthesis should appear on public pages.

Public Funding pages should only show:

```text
reviewed/public records
accepted public-safe relationships
reviewed public summary/card copy
source link
effort label/caveat
```

Never show:

```text
private summary
private rationale
LLM raw output
LLM errors
match scores
collaboration hypotheses
outreach language
```

## Acceptance Criteria

This sprint is complete when:

```text
Admin can see current vs synthesized funding fields.
Admin can apply selected synthesized fields only.
Admin can ignore individual draft fields.
Manual values are not overwritten silently.
Changed/new/missing fields are visually obvious.
Public-card regeneration is a distinct explicit action.
Effort from synthesis can be applied separately.
Failed fetch/synthesis states are visible on the Funding detail page.
Fetch retry is available and bounded.
All LLM calls are logged in LLMRun.
Public Funding pages do not expose draft/unreviewed synthesis.
Existing CSV import still works.
Existing public Funding Radar still works.
Existing tests pass.
```

## Required Tests

Add or update tests for:

```text
funding synthesis diff generation
apply selected fields only
manual override preservation
tag normalization during apply
deadline/date apply behavior
public-card regeneration draft behavior
effort draft apply behavior
fetch error display/retry route
LLMRun link/status display
public page excludes unreviewed draft values
```

Run at minimum:

```bash
pytest tests/test_funding_model.py tests/test_funding_csv_import.py
pytest tests/test_public_funding_routes.py
pytest tests/test_admin_settings_routes.py
pytest tests/test_prompt_registry.py tests/test_prompt_validation.py
```

Also run the full suite before completion:

```bash
pytest
```

## Manual Testing Path

1. Start with a clean migrated dev database.
2. Import `data/funding_opportunities_sample.csv`.
3. Open `/admin/funding/`.
4. Pick one public-ready record and one incomplete record.
5. Fetch source text if the URL is reachable.
6. Run synthesis.
7. Review field-by-field diffs.
8. Apply only selected fields.
9. Regenerate public card.
10. Apply or reject card copy.
11. Apply draft effort or keep deterministic effort.
12. Mark record reviewed/public.
13. Check `/funding/` and `/funding/<slug>`.
14. Confirm draft/private values do not leak publicly.

## Sprint Non-Goals

The goal is not to make funding extraction perfect.

The goal is to make funding synthesis:

```text
bounded
logged
reviewable
recoverable
safe for public publication
```

A human operator remains in control.
