# Sprint 03 — Relationship Editor and Match Rationales

## Primary References

Read these first, but implement only the scope in this sprint:

```text
docs/synapse_progress_against_vision.md
docs/recent_progress_and_remaining.md
docs/matching_and_leads.md
docs/idea_model.md
docs/prompt_specs.md
docs/sprints/sprint_01_funding_review.md
docs/sprints/sprint_02_contentitem_ideas.md
```

## Sprint Goal

Make Synapse relationships easier to create, inspect, and trust.

The system already has:

- `MatchRun`
- `MatchEdge`
- deterministic Funding ↔ Idea matching
- person-to-Idea matching
- organization-to-Idea matching
- funding-to-person and funding-to-organization matching through accepted Idea bridge edges
- manual relationship creation using `MatchEdge`
- public-safe relationship visibility gates
- live LLM execution through the prompt registry
- `LLMRun` logging
- admin Matching dashboard
- public Idea/Funding cross-links from accepted public-safe edges

This sprint should improve operator control and trust by adding a practical relationship editor, better match detail pages, and optional LLM-generated rationales for selected matches.

## Why This Sprint Matters

The original vision depends on a useful opportunity graph.

That graph is only valuable if operators can answer:

```text
What is connected?
Why is it connected?
Is this relationship private or public-safe?
What evidence supports it?
Should this be accepted, rejected, archived, or used in a collaboration hypothesis?
```

This sprint focuses on making relationships inspectable and curated, not merely generated.

## In Scope

### 1. Manual relationship editor

Add a friendly admin workflow for creating relationships between existing objects.

Minimum supported relationship types:

```text
Idea ↔ Person
Idea ↔ Organization
Idea ↔ Funding
Funding ↔ Person
Funding ↔ Organization
```

Optional if easy:

```text
Idea ↔ Building/Place
Idea ↔ Region
Funding ↔ Building/Place
Hub ↔ Target
```

Use `MatchEdge` if it is already flexible enough. Do not add a new relationship table unless `MatchEdge` clearly cannot support this workflow.

The editor should allow the operator to set:

```text
source entity
target entity
relationship/match type
status
visibility
rationale or note
evidence summary
public-safe short summary if supported
```

### 2. Friendly entity pickers

The editor should not require raw database IDs if avoidable.

Use simple search/select controls or dropdowns for:

```text
Ideas
Funding
People
Organizations
Buildings/Places if supported
```

If full autocomplete is too much, start with searchable/selectable lists or type-specific forms.

### 3. MatchEdge detail page

Add a detail page for a relationship/match edge.

Suggested route:

```text
/admin/matching/edges/<edge_id>
```

Detail page should show:

```text
source entity
target entity
match type
status
visibility
score/subscores if available
private rationale
public-safe summary if available
evidence snippets
created by: deterministic | manual | llm
associated MatchRun if any
associated LLMRun if any
created/updated timestamps
```

Actions:

```text
accept
reject
archive
mark private
mark public-safe
edit note/rationale
generate LLM rationale
delete if safe and consistent with existing patterns
```

### 4. LLM rationale generation for selected matches

Add an explicit action on the match detail page:

```text
Generate rationale
```

This should run only for the selected match, not for all matches in a batch.

The LLM should produce a private rationale explaining:

```text
why the entities are connected
what evidence supports the relationship
how strong the match seems
what is uncertain
whether the relationship could be public-safe
```

Optional output:

```text
public_safe_summary
```

Public-safe summary must remain review-gated and not appear publicly until the edge visibility/status allows it.

### 5. Evidence-aware rationale context

The rationale prompt should receive compact context from:

```text
source entity
target entity
existing tags
summaries/personas if available
funding summary/effort if relevant
Idea summary if relevant
existing match score/subscores if available
supporting evidence snippets if available
```

Do not overpack context.

Respect Settings prompt caps.

### 6. Public-safety review

Make the public/private distinction clear on the match detail page.

Visibility options should remain explicit:

```text
private
public_safe
public
```

Public pages should continue to show only accepted edges with `public_safe` or `public` visibility.

## Out of Scope

Do not implement these in this sprint:

```text
Collaboration Hypothesis upgrades
Hub-to-target matching if not already simple
place/building matching if it expands scope too much
major public atlas redesign
public Places pages
persistent editable Settings
LeadReport migration
email/outreach automation
automatic batch LLM rationales
vector search
full CRM workflows
```

## Recommended Architecture

### Reuse MatchEdge

Prefer extending current matching infrastructure.

A manual relationship can be represented as a `MatchEdge` with something like:

```text
created_by = "manual"
match_type = "idea_to_person" or equivalent
status = "accepted" or "pending"
visibility = "private" by default
score = null or manually set
```

If current fields differ, adapt to existing conventions.

### Suggested service boundary

Add or extend:

```text
app/matching/relationships.py
app/matching/rationale.py
```

Suggested functions:

```text
create_manual_match_edge(...)
update_match_edge_review(...)
generate_match_rationale(edge_id, provider_policy=None)
build_match_rationale_context(edge)
```

### Rationale prompt

Use an existing matching prompt if suitable. If not, add:

```text
prompts/match_rationale.txt
```

Expected structured output:

```json
{
  "private_rationale": "",
  "evidence_summary": "",
  "uncertainties": [],
  "recommended_status": "accept|reject|needs_review",
  "public_safe_candidate": true,
  "public_safe_summary": "",
  "confidence": 0.0
}
```

All live calls must go through:

```text
prompt registry
settings/cap checks
provider boundary
JSON validation
LLMRun logging
```

### Status and visibility

Keep status and visibility separate.

Recommended concepts:

```text
status: pending | accepted | rejected | archived
visibility: private | public_safe | public
```

Do not make public-safe imply accepted automatically unless the existing model already does.

## UI/UX Requirements

Maintain existing admin aesthetic.

Use existing:

```text
cards
tables
badges
help popovers
button styles
expandable sections
```

The Matching dashboard should provide clear entry points:

```text
Create manual relationship
View pending matches
View accepted public-safe relationships
View failed rationale runs if applicable
```

Match detail page should be readable and action-oriented.

Suggested sections:

```text
1. Relationship summary
2. Source entity
3. Target entity
4. Scores and status
5. Evidence and rationale
6. Public visibility
7. LLM run history
8. Review actions
```

## Public-Safety Requirements

Public pages may only show relationships that are:

```text
accepted
public_safe or public
not archived
between reviewed/public entities where applicable
```

Public pages must not show:

```text
private rationale
private score details
LLM raw output
LLM errors
rejected edges
pending edges
collaboration hypotheses
outreach language
```

## Acceptance Criteria

This sprint is complete when:

```text
Admin can manually create a relationship/match edge between supported entity types.
Admin can select entities without raw database IDs where practical.
Admin can open a match/relationship detail page.
Admin can accept, reject, archive, and change visibility from the detail page.
Admin can add or edit a private note/rationale.
Admin can generate an LLM rationale for one selected match.
LLM rationale generation uses prompt registry, validation, Settings caps, and LLMRun.
Generated rationale remains private by default.
Optional public-safe summary is review-gated.
Public pages only show accepted public-safe/public edges.
Existing deterministic matching still works.
Existing ContentItem-to-Idea and funding workflows still work.
Existing tests pass.
```

## Required Tests

Add or update tests for:

```text
manual MatchEdge creation
entity type validation
friendly route/form behavior
match detail page rendering
accept/reject/archive actions
visibility update actions
private rationale edit
LLM rationale generation with mock provider
LLMRun linkage
invalid LLM output handling
public-safe summary review behavior
public pages exclude private/pending/rejected edges
existing deterministic matching regression
```

Run at minimum:

```bash
pytest tests/test_match_models.py
pytest tests/test_matching_scoring.py
pytest tests/test_admin_matching_routes.py
pytest tests/test_public_funding_routes.py
pytest tests/test_public_ideas_routes.py
pytest tests/test_prompt_registry.py tests/test_prompt_validation.py
```

Also run the full suite before completion:

```bash
pytest
```

## Manual Testing Path

1. Start with a migrated dev database.
2. Import sample funding.
3. Create or accept a few Ideas.
4. Open `/admin/matching`.
5. Create a manual relationship between an Idea and a Funding record.
6. Open the match detail page.
7. Add/edit a private rationale.
8. Accept the relationship.
9. Mark it public-safe.
10. Verify the relationship appears on public Idea/Funding pages.
11. Change visibility back to private.
12. Confirm it disappears publicly.
13. Generate an LLM rationale with a mock/local provider.
14. Confirm `LLMRun` is recorded.
15. Confirm rationale remains private.
16. Reject/archive a relationship and verify it does not appear publicly.

## Sprint Non-Goals

The goal is not to make matching perfect.

The goal is to make relationships:

```text
createable
inspectable
reviewable
explainable
public-safe when appropriate
private by default
```

A human operator remains in control.
