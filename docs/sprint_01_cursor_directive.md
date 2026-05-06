# Cursor Directive — Sprint 01 Funding Review

## Mission

Implement only Sprint 01: Funding Review and Trust Workflow.

Do not broaden scope.

The goal is to make funding synthesis reviewable, safe, and operator-friendly.

## Read First

Use these as context:

```text
docs/synapse_progress_against_vision.md
docs/recent_progress_and_remaining.md
docs/funding_model.md
docs/effort_index.md
docs/prompt_specs.md
docs/sprints/sprint_01_funding_review.md
```

If local filenames differ, use the closest matching roadmap/progress/funding/prompt docs.

## Hard Scope Boundary

Implement:

```text
field-by-field funding synthesis review
apply/ignore selected synthesized fields
manual override preservation
changed/new/missing field indicators
distinct public-card regeneration action
separate effort apply controls
failed fetch/synthesis recovery UX
tests for all of the above
```

Do not implement:

```text
Idea suggestions from ContentItem
manual relationship editor
expanded matching
LLM match rationale
Collaboration Hypothesis upgrades
public atlas redesign
public Places pages
persistent editable Settings
LeadReport migration
outreach/email features
```

## Implementation Guidance

Before editing:

```text
1. Inspect existing Funding models, routes, services, and templates.
2. Reuse existing admin visual patterns.
3. Find how synthesis drafts are currently stored.
4. Find how LLMRun links/errors are shown in Settings.
5. Find existing tests for Funding admin/public routes.
```

Prefer small, testable changes.

## Suggested Implementation Order

### Step 1 — Inspect current funding synthesis storage

Determine where synthesized fields live.

Possible patterns:

```text
FundingOpportunity.synthesized_json
FundingOpportunity.synthesis_draft_json
related draft model
```

Do not create a new table unless the current storage is clearly insufficient.

### Step 2 — Add diff helper

Create or extend a service such as:

```text
app/funding/synthesis_review.py
```

Add:

```text
get_funding_synthesis_diff(funding)
```

Return field-level diff objects with:

```text
field
label
current_value
draft_value
status: new | changed | unchanged | missing
is_manual
can_apply
```

### Step 3 — Add selected-field apply helper

Add:

```text
apply_funding_synthesis_fields(funding, selected_fields)
```

Requirements:

```text
apply only selected fields
normalize tag arrays
handle deadline_date safely
do not overwrite fields that were not selected
record apply timestamp if available
preserve reviewed/public flags
```

### Step 4 — Update Funding detail UI

Add a synthesis review section.

For each field:

```text
show current value
show draft value
show status badge
checkbox or button to apply
```

Keep it compact and consistent with existing admin style.

### Step 5 — Add public-card regeneration action

Add an explicit action:

```text
Regenerate public card
```

It should call the relevant prompt through the existing LLM execution path.

Result should be reviewable before public display.

### Step 6 — Add separate effort controls

Support:

```text
Use draft effort
Keep current effort
Rebuild deterministic effort
Manual override remains possible
```

### Step 7 — Improve fetch/synthesis error visibility

On Funding detail, show:

```text
last fetch timestamp
HTTP status
content type
raw text chars
raw text hash
fetch error
latest LLMRun status/error if available
```

Add bounded retry action if not already present.

### Step 8 — Tests

Add focused tests before running the full suite.

Use mock providers. Do not require real Ollama or OpenAI.

## Acceptance Checklist

Complete only when all are true:

```text
[ ] Field-level diff UI exists.
[ ] Admin can apply selected draft fields.
[ ] Ignored fields remain unchanged.
[ ] Manual/current values are not silently overwritten.
[ ] Public-card regeneration is a separate action.
[ ] Public-card output remains review-gated.
[ ] Draft effort can be applied separately.
[ ] Deterministic effort rebuild still works.
[ ] Fetch/synthesis errors are visible and recoverable.
[ ] LLMRun logging is preserved.
[ ] Public Funding pages do not show unreviewed draft values.
[ ] CSV import still works.
[ ] Full test suite passes.
```

## Testing Commands

Run focused tests first:

```bash
pytest tests/test_funding_model.py tests/test_funding_csv_import.py
pytest tests/test_public_funding_routes.py
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
How synthesis review works
How public-card regeneration works
How manual values are protected
Tests run and results
Known limitations
```
