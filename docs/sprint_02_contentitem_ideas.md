# Sprint 02 — ContentItem to Idea Suggestions

## Primary References

Read these first, but implement only the scope in this sprint:

```text
docs/synapse_progress_against_vision.md
docs/recent_progress_and_remaining.md
docs/idea_model.md
docs/matching_and_leads.md
docs/prompt_specs.md
docs/sprints/sprint_01_funding_review.md
```

## Sprint Goal

Extend the Idea workflow so Ideas can be suggested from individual `ContentItem` records and, if practical, small selected sets of `ContentItem` records.

The system already has:

- `Idea`
- `IdeaSuggestion`
- Idea suggestions from `PersonaSnapshot`
- prompt registry and live LLM execution
- `LLMRun` logging
- admin Idea suggestion review
- accept / reject / merge flow
- public Ideas pages

This sprint should make Ideas emerge from source evidence, not just persona snapshots.

## Why This Sprint Matters

Ideas are the connective tissue of Synapse.

The original vision depends on moving from:

```text
people/orgs/funding as isolated records
```

toward:

```text
evidence → ideas → relationships → collaboration hypotheses
```

`ContentItem`-based suggestions make the system more responsive to recent papers, RSS entries, submitted URLs, public latest items, and other newly ingested material.

## In Scope

### 1. Generate Idea suggestions from one ContentItem

Add an admin action that creates one or more `IdeaSuggestion` records from a selected `ContentItem`.

Possible locations:

```text
/admin/content-items/<id>
admin content item detail page
admin public/latest curation detail if applicable
/admin/ideas/suggestions
```

The route location should match the existing admin organization.

The action should:

```text
load ContentItem evidence
render the idea extraction prompt
run through live LLM execution
validate structured output
create pending IdeaSuggestion rows
link each suggestion to the source ContentItem
link each suggestion to the LLMRun
```

### 2. Optional: Generate from a small selected set of ContentItems

If the current admin UI already supports selecting multiple content items, add a batch action.

If this would require too much UI work, defer batch selection and implement a service-level function plus tests.

Batch generation must be bounded:

```text
max selected items
max total evidence chars
single LLMRun
clear error if evidence is too large
```

### 3. Show ContentItem provenance on IdeaSuggestion

The suggestion review UI should clearly show:

```text
source ContentItem title
source URL if available
source type
published/created date if available
evidence snippet
LLMRun status/provider/model
```

### 4. Accept/reject/merge from ContentItem suggestions

Reuse the existing IdeaSuggestion review workflow.

Ensure accepted Ideas preserve provenance from the ContentItem.

If a suggestion is merged into an existing Idea, keep evidence/provenance attached somehow.

### 5. Duplicate detection improvements

Before creating a new `IdeaSuggestion` or accepting it as an `Idea`, run deterministic duplicate checks against existing Ideas.

Minimum checks:

```text
normalized title match
alias match
high tag overlap
slug/title similarity
```

Recommended outputs:

```text
duplicate_candidate_id
duplicate_confidence
duplicate_reason
```

The UI should show likely duplicates before acceptance.

### 6. Public safety

Generated Ideas remain private and unreviewed by default.

Public Idea pages should not show newly generated suggestions until accepted, reviewed, and public.

## Out of Scope

Do not implement these in this sprint:

```text
manual relationship editor
expanded matching
LLM match rationale generation
Collaboration Hypothesis upgrades
public atlas redesign
public Places pages
persistent editable Settings
LeadReport migration
email/outreach automation
bulk review system beyond existing suggestion review
```

## Recommended Architecture

### Reuse existing IdeaSuggestion workflow

Avoid creating a parallel suggestion path.

Extend the existing suggestion service to support multiple source types:

```text
PersonaSnapshot
ContentItem
```

Possible service names:

```text
app/ideas/suggestions.py
app/ideas/contentitem_suggestions.py
```

Preferred API shape:

```text
generate_idea_suggestions_from_content_item(content_item_id, *, provider_policy=None) -> list[IdeaSuggestion]
generate_idea_suggestions_from_content_items(content_item_ids, *, provider_policy=None) -> list[IdeaSuggestion]
```

### Source typing

If `IdeaSuggestion` already has generic source fields, reuse them:

```text
source_type = "content_item"
source_id = ContentItem.id
```

If not, minimally extend the model.

Do not hard-code only persona snapshots.

### Evidence packing

The prompt should receive compact evidence:

```text
title
source URL
published date
source name/type
snippet
cleaned body excerpt if available
existing tags if available
```

Use existing content budgets and Settings caps.

### Prompt execution

All LLM calls must go through:

```text
prompt registry
settings/cap checks
provider boundary
JSON validation
LLMRun logging
```

Use the existing idea extraction prompt if suitable. If it is persona-specific, add a ContentItem-specific prompt:

```text
prompts/idea_extract_from_content_item.txt
```

Expected structured output:

```json
{
  "ideas": [
    {
      "title": "",
      "short_description": "",
      "public_summary": "",
      "tags": [],
      "aliases": [],
      "hub_capabilities": [],
      "evidence_summary": "",
      "confidence": 0.0
    }
  ]
}
```

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

Idea suggestion review should show:

```text
suggestion title
suggestion summary
tags
Hub capability hints
source ContentItem
evidence snippet
possible duplicate
confidence
actions: accept, reject, merge
```

## Public-Safety Requirements

Public pages may only show Ideas that are:

```text
accepted
reviewed
public
not archived
```

Public pages must not show:

```text
pending suggestions
rejected suggestions
LLM raw output
LLM errors
private evidence notes
unreviewed summaries
```

## Acceptance Criteria

This sprint is complete when:

```text
Admin can generate Idea suggestions from a ContentItem.
Generated suggestions are linked to the source ContentItem.
Generated suggestions are linked to an LLMRun.
Generated suggestions remain pending/private by default.
Suggestion review UI shows ContentItem provenance.
Admin can accept, reject, or merge ContentItem-generated suggestions.
Accepted Ideas preserve source evidence/provenance.
Duplicate candidates are detected and displayed.
Public Ideas pages do not expose pending suggestions.
PersonaSnapshot-based Idea suggestions still work.
Existing tests pass.
```

## Required Tests

Add or update tests for:

```text
ContentItem → IdeaSuggestion service
prompt execution using mock provider
LLMRun linkage
source_type/source_id persistence
duplicate detection against existing Ideas
accept suggestion as Idea
reject suggestion
merge suggestion into existing Idea
public visibility gating
PersonaSnapshot suggestion regression
```

Run at minimum:

```bash
pytest tests/test_idea_model.py
pytest tests/test_admin_ideas_routes.py
pytest tests/test_prompt_registry.py tests/test_prompt_validation.py
pytest tests/test_admin_settings_routes.py
```

Also run the full suite before completion:

```bash
pytest
```

## Manual Testing Path

1. Start with a migrated dev database.
2. Ensure LLM synthesis is enabled for local/mock/Ollama testing.
3. Ingest or create at least one `ContentItem`.
4. Open the admin ContentItem detail page or relevant admin list.
5. Run `Generate Idea suggestions`.
6. Open `/admin/ideas/suggestions`.
7. Confirm the suggestion shows source ContentItem provenance.
8. Accept one suggestion as a new Idea.
9. Reject one suggestion if multiple are generated.
10. Merge one suggestion into an existing Idea if a duplicate exists.
11. Confirm accepted Ideas appear in admin Ideas.
12. Mark one accepted Idea reviewed/public.
13. Confirm `/ideas/` shows only reviewed/public Ideas.
14. Confirm pending suggestions do not appear publicly.

## Sprint Non-Goals

The goal is not to build a perfect research ontology.

The goal is to make `ContentItem` evidence capable of producing reviewable, private Idea suggestions that can become public Ideas after human review.

A human operator remains in control.
