# Cursor Directive — Sprint 02 ContentItem Idea Suggestions

## Mission

Implement only Sprint 02: ContentItem to Idea Suggestions.

Do not broaden scope.

The goal is to let operators generate reviewable `IdeaSuggestion` records from `ContentItem` evidence.

## Read First

Use these as context:

```text
docs/synapse_progress_against_vision.md
docs/recent_progress_and_remaining.md
docs/idea_model.md
docs/matching_and_leads.md
docs/prompt_specs.md
docs/sprints/sprint_02_contentitem_ideas.md
```

If local filenames differ, use the closest matching roadmap/progress/idea/prompt docs.

## Hard Scope Boundary

Implement:

```text
generate IdeaSuggestion from one ContentItem
link suggestion to ContentItem source
link suggestion to LLMRun
show ContentItem provenance in suggestion review
accept/reject/merge generated suggestions
improve deterministic duplicate detection
tests for all of the above
```

Do not implement:

```text
manual relationship editor
expanded matching
LLM match rationale
Collaboration Hypothesis upgrades
public atlas redesign
public Places pages
persistent editable Settings
LeadReport migration
outreach/email features
major review queue redesign
```

## Implementation Guidance

Before editing:

```text
1. Inspect existing Idea and IdeaSuggestion models.
2. Inspect existing persona-based Idea suggestion workflow.
3. Inspect ContentItem model and admin routes.
4. Inspect prompt registry and LLM execution pipeline.
5. Inspect existing Idea suggestion tests.
```

Prefer extending existing workflows over creating parallel ones.

## Suggested Implementation Order

### Step 1 — Inspect existing IdeaSuggestion source fields

Determine whether the model already supports generic source references.

Preferred shape:

```text
source_type
source_id
```

If it only supports `PersonaSnapshot`, extend minimally to support `ContentItem`.

### Step 2 — Add ContentItem evidence packer

Create or extend a helper that produces compact prompt input from a `ContentItem`.

Include:

```text
title
URL
source name/type
published/created date
snippet
clean body excerpt if available
```

Respect existing char caps.

### Step 3 — Add service function

Add something like:

```text
generate_idea_suggestions_from_content_item(content_item_id)
```

Requirements:

```text
use prompt registry
use live LLM execution pipeline
validate structured output
create pending IdeaSuggestion rows
set source_type = "content_item"
set source_id = content item id
store llm_run_id
run duplicate detection
```

### Step 4 — Add admin action

Add an explicit admin action from a logical place:

```text
ContentItem detail page
ContentItem list row action
/admin/ideas/suggestions page
```

Follow existing admin route patterns.

### Step 5 — Update suggestion review UI

Show provenance:

```text
source ContentItem title
source URL
source date
evidence snippet
LLMRun provider/model/status
possible duplicate candidate
```

Keep the UI compact and consistent with existing admin styling.

### Step 6 — Duplicate detection

Implement deterministic duplicate detection against existing Ideas.

Minimum:

```text
normalized title
aliases
slug similarity
tag overlap
```

Store/display:

```text
duplicate_candidate_id
duplicate_reason
duplicate_confidence
```

Do not rely on LLM duplicate detection in this sprint.

### Step 7 — Tests

Use mock providers. Do not require real Ollama or OpenAI.

## Acceptance Checklist

Complete only when all are true:

```text
[ ] Admin can generate Idea suggestions from one ContentItem.
[ ] Suggestions are linked to source_type/content_item and source_id.
[ ] Suggestions are linked to LLMRun.
[ ] Suggestions are pending/private by default.
[ ] Suggestion review UI shows ContentItem provenance.
[ ] Admin can accept ContentItem suggestions as Ideas.
[ ] Admin can reject ContentItem suggestions.
[ ] Admin can merge ContentItem suggestions into existing Ideas.
[ ] Duplicate candidates are detected and visible.
[ ] Pending suggestions do not appear publicly.
[ ] PersonaSnapshot-based suggestions still work.
[ ] Full test suite passes.
```

## Testing Commands

Run focused tests first:

```bash
pytest tests/test_idea_model.py
pytest tests/test_admin_ideas_routes.py
pytest tests/test_prompt_registry.py tests/test_prompt_validation.py
pytest tests/test_admin_settings_routes.py
```

Then:

```bash
pytest
```

## Final Response Expected From Agent

When done, report:

```text
Files changed
Routes/actions added
How ContentItem evidence is packed
How IdeaSuggestion records are linked to source ContentItems
How duplicate detection works
How review/accept/reject/merge works
Tests run and results
Known limitations
```
