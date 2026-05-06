# Cursor Directive — Sprint 03 Relationship Editor and Match Rationales

## Mission

Implement only Sprint 03: Relationship Editor and Match Rationales.

Do not broaden scope.

The goal is to make match/relationship edges easy to create, inspect, review, and explain.

## Read First

Use these as context:

```text
docs/synapse_progress_against_vision.md
docs/recent_progress_and_remaining.md
docs/matching_and_leads.md
docs/idea_model.md
docs/prompt_specs.md
docs/sprints/sprint_03_relationships_match_rationales.md
```

If local filenames differ, use the closest matching roadmap/progress/matching/prompt docs.

## Hard Scope Boundary

Implement:

```text
manual relationship editor using MatchEdge or existing equivalent
friendly entity selectors where practical
match/relationship detail page
accept/reject/archive/visibility controls from detail page
private note/rationale editing
LLM rationale generation for one selected match
LLMRun linkage and validation handling
public-safe filtering regression tests
```

Do not implement:

```text
Collaboration Hypothesis upgrades
public atlas redesign
public Places pages
persistent editable Settings
LeadReport migration
email/outreach features
automatic batch LLM rationales
vector search
major scoring overhaul
full CRM workflows
```

## Implementation Guidance

Before editing:

```text
1. Inspect MatchRun, MatchEdge, and CollaborationHypothesis models.
2. Inspect current Matching dashboard routes/templates.
3. Inspect deterministic matching services.
4. Inspect public Idea/Funding related-card queries.
5. Inspect LLM execution and prompt registry APIs.
6. Inspect existing admin route/test style.
```

Prefer extending existing matching infrastructure over creating a parallel relationship system.

## Suggested Implementation Order

### Step 1 — Inspect MatchEdge flexibility

Confirm fields for:

```text
source type/id
target type/id
match type
status
visibility
score
rationale
public summary
created_by or generation source
llm_run_id if available
```

If fields are missing, add the minimum necessary migration.

Do not create a new `EntityRelationship` table unless `MatchEdge` is unusable.

### Step 2 — Add manual relationship service

Create or extend something like:

```text
app/matching/relationships.py
```

Add:

```text
create_manual_match_edge(...)
update_match_edge_status(...)
update_match_edge_visibility(...)
update_match_edge_note(...)
```

Validate entity types.

Default manual relationships to:

```text
status = pending or accepted, whichever matches current review pattern
visibility = private
created_by = manual
```

### Step 3 — Add relationship editor UI

Add route/form reachable from:

```text
/admin/matching
```

Support common types first:

```text
Idea ↔ Person
Idea ↔ Organization
Idea ↔ Funding
Funding ↔ Person
Funding ↔ Organization
```

Use dropdowns/searchable lists instead of raw IDs where practical.

### Step 4 — Add match detail page

Suggested route:

```text
/admin/matching/edges/<edge_id>
```

Show:

```text
source entity
target entity
match type
status
visibility
score/subscores
private rationale/note
public-safe summary
evidence snippets
MatchRun
LLMRun
timestamps
```

Actions:

```text
accept
reject
archive
mark private
mark public-safe
mark public if supported
edit rationale/note
generate rationale
```

### Step 5 — Add LLM rationale generation

Add a selected-match action only.

Do not batch-generate rationales.

Use prompt registry + LLM execution.

Expected result:

```text
private rationale
evidence summary
uncertainties
recommended status
public-safe candidate flag
optional public-safe summary
confidence
```

Store result on the edge or in existing appropriate fields.

Link to `LLMRun`.

### Step 6 — Preserve public safety

Ensure public pages only use:

```text
accepted edges
public_safe or public visibility
reviewed/public entities
```

Private rationale must never appear publicly.

### Step 7 — Tests

Use mock providers.

Do not require real Ollama or OpenAI.

## Acceptance Checklist

Complete only when all are true:

```text
[ ] Admin can create manual relationships between supported entity types.
[ ] Entity selection does not require raw DB IDs where practical.
[ ] Match detail page exists.
[ ] Admin can accept/reject/archive from detail page.
[ ] Admin can set visibility private/public_safe/public as supported.
[ ] Admin can edit private rationale/note.
[ ] Admin can generate rationale for a selected match.
[ ] Rationale call uses prompt registry and LLMRun.
[ ] Invalid LLM output is handled and logged.
[ ] Rationale is private by default.
[ ] Public-safe summary is review-gated.
[ ] Public pages do not expose private/pending/rejected edges.
[ ] Existing deterministic matching still works.
[ ] Full test suite passes.
```

## Testing Commands

Run focused tests first:

```bash
pytest tests/test_match_models.py
pytest tests/test_matching_scoring.py
pytest tests/test_admin_matching_routes.py
pytest tests/test_public_funding_routes.py
pytest tests/test_public_ideas_routes.py
pytest tests/test_prompt_registry.py tests/test_prompt_validation.py
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
How manual relationships are created
How match detail pages work
How LLM rationale generation works
How public/private safety is enforced
Tests run and results
Known limitations
```
