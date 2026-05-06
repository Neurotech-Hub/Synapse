# Synapse Next-Todo Response for Planning Agent

## Purpose

This response reviews the current testing handoff and defines the next most important work chunks needed to move Synapse toward the original vision:

> A research opportunity graph for the Neurotech Hub that connects people, organizations, places, ideas, funding, and evidence into useful public discovery and private collaboration hypotheses.

The current implementation has a strong foundation. Funding, Ideas, deterministic effort classification, deterministic funding-to-Idea matching, public Funding/Idea pages, and prompt files now exist. The next sprint should avoid scattering effort across too many features and instead focus on the missing connective tissue: safe LLM execution, funding extraction, Idea generation, richer matching, and a more exploratory public UX.

---

## Executive Priority

The next work should be organized around this sequence:

1. **Operational safety and settings**
2. **LLM run logging and prompt execution infrastructure**
3. **Funding URL fetch/extract/synthesis**
4. **Idea suggestion and relationship workflows**
5. **Expanded matching and collaboration hypotheses**
6. **Public discovery layer: Explore/Search/homepage integration**
7. **Admin review queues and operator visibility**

Do not expand public graph complexity or broad matching until the Settings + LLMRun foundation exists.

---

## Current State Summary

Implemented foundations include:

- Funding model, migrations, admin CRUD, CSV import, dry-run validation, duplicate detection, review/archive, and public/private visibility.
- Deterministic effort index classification with rationale, confidence, and signals.
- Manual Ideas with admin CRUD, public pages, tags, aliases, and Hub capability fields.
- Matching foundations with `MatchRun`, `MatchEdge`, and `CollaborationHypothesis`.
- Deterministic funding-to-Idea matching and admin review actions.
- Public Funding Radar and public Idea pages.
- Prompt files plus offline prompt registry/validation.
- Admin navigation and help popovers for Funding, Ideas, and Matching.

The main remaining gap is that the app still behaves like a manually curated data system with limited deterministic matching. It does not yet behave like a semi-automated research-intelligence engine.

---

# Chunk 1 — Add Settings and LLM Safety Controls

## Why this comes first

Before live LLM calls are wired, the app needs operator controls. This protects against accidental cost spikes, repeated calls, recursive workflows, and unclear provider behavior.

## Build

Create an Admin Settings area, likely:

```text
/admin/settings
```

Initial sections:

```text
Feature Flags
  Public Ideas enabled
  Public Funding enabled
  Matching enabled
  LLM synthesis enabled
  OpenAI escalation enabled

Provider Status
  Ollama host/model/reachability
  OpenAI key present/not present
  OpenAI SDK available/not available

Call Limits
  max prompt chars
  max source text chars
  max batch size
  max matches per run
  max LLM calls per admin action
  retry cap
  timeout seconds

Provider Policy
  default funding provider
  default idea provider
  default matching provider
  default collaboration hypothesis provider
  allow OpenAI fallback?
  require confirmation before OpenAI call?

Safety
  no recursive crawling
  one URL per funding fetch
  no automatic public publishing from LLM output
  no automatic outreach generation without admin action
```

Settings can start as environment-backed/read-only if persistent DB-backed settings would slow implementation.

## Acceptance Criteria

- Admin can see which new feature flags are active.
- Admin can see whether Ollama/OpenAI are available.
- Settings page explains which actions may call an LLM.
- OpenAI escalation is disabled unless explicitly enabled.
- No live LLM feature can run without checking settings/caps.

## Out of Scope

- Multi-user settings.
- Full role-based access control.
- Billing dashboards.
- Autonomous background LLM runs.

---

# Chunk 2 — Add `LLMRun` / `PromptRun` Logging

## Why this matters

Prompt files and validation exist, but live calls are not wired. Before wiring them, add a durable record of every prompt execution. This gives debugging, reproducibility, cost control, and operator trust.

## Build

Add a model such as:

```text
LLMRun
  id
  prompt_name
  prompt_version
  provider
  model
  input_fingerprint
  rendered_prompt_hash
  output_hash
  status
  error_message
  latency_ms
  estimated_input_tokens
  estimated_output_tokens
  estimated_cost_usd nullable
  source_type nullable
  source_id nullable
  created_at
  completed_at
```

Possible service location:

```text
app/llm/run.py
app/llm/providers.py
app/llm/json_repair.py
```

All new LLM features should flow through:

```text
prompt registry → render → provider call → JSON validation → optional repair → LLMRun record → reviewed output
```

## Acceptance Criteria

- Every live prompt call creates an `LLMRun`.
- Failed calls are logged with readable errors.
- Output validation status is recorded.
- Prompt name/version and provider/model are visible in admin.
- Existing offline prompt tests still pass.
- No LLM call bypasses the registry.

## Out of Scope

- Perfect token accounting.
- Complex cost forecasting.
- Streaming output.
- Background queue infrastructure.

---

# Chunk 3 — Funding URL Fetch, Extract, and Synthesize

## Why this is the next product-critical feature

Funding is the missing object that makes lead generation actionable. CSV import is a good testing path, but the app needs to ingest/summarize funding links from NIH, NSF, foundations, nonprofits, and internal programs with inconsistent metadata.

## Build

Add bounded fetch/extract helpers:

```text
app/funding/fetch.py
app/funding/extract.py
app/funding/synthesis.py
```

Admin action on funding detail:

```text
Fetch source text
Synthesize funding fields
Regenerate public card
Reclassify effort
```

Store:

```text
final_url
status_code
content_type
fetched_at
fetch_error
raw_text
raw_text_hash
source_text_chars
synthesis_status
synthesis_confidence
```

The fetcher must be conservative:

```text
one URL only
timeout required
max response size
no recursive crawling
no automatic following across arbitrary domains beyond normal redirect
ignore binary files unless explicitly supported later
```

## Synthesis Output

Use the existing prompt registry to produce a lightweight normalized output:

```json
{
  "title": "",
  "sponsor": "",
  "one_sentence_summary": "",
  "public_summary": "",
  "eligibility_summary": "",
  "amount_text": "",
  "deadline_text": "",
  "deadline_date": null,
  "topic_tags": [],
  "method_tags": [],
  "possible_hub_relevance": [],
  "effort_index": "mild|moderate|heavy|unknown",
  "effort_rationale": "",
  "confidence": 0.0,
  "missing_information": []
}
```

## Provider Policy

Default:

```text
Ollama first
OpenAI only if:
  admin explicitly requests it
  OpenAI escalation is enabled
  the record is high-value
  local extraction failed or confidence is low
```

## Acceptance Criteria

- Admin can fetch source text for a funding record.
- Admin can see fetch status/errors.
- Admin can run synthesis explicitly.
- LLM output never auto-publishes without review.
- Funding records can be updated from synthesis while preserving manual overrides.
- Effort index can be regenerated from fetched/synthesized text.
- CSV import still works as the primary test path.

## Out of Scope

- General web crawler.
- Automated scraping schedules.
- Login-protected pages.
- Perfect NIH/NSF/foundation-specific parsing.

---

# Chunk 4 — Idea Suggestion and Relationship Workflows

## Why this matters

Manual Ideas exist, but the original vision depends on Ideas emerging from the known corpus of people, organizations, places, and content. Ideas are the connective layer that makes the public site exploratory and makes matching more meaningful.

## Build

Add Idea suggestion workflows from:

```text
PersonaSnapshot
ContentItem
Organization rollup
Building/place rollup
```

Recommended approach:

```text
Generate candidate Ideas → review screen → accept/reject/merge → public/private status
```

Possible model:

```text
IdeaSuggestion
  id
  source_type
  source_id
  title
  short_description
  tags_json
  hub_capabilities_json
  evidence_json
  duplicate_candidate_id nullable
  status: pending | accepted | rejected | merged
  created_by_provider
  llm_run_id nullable
  created_at
```

Relationship options:

1. Extend `MatchEdge` to support Idea-to-entity links.
2. Add a lightweight `EntityRelationship` table.
3. Start with `MatchEdge` for consistency, then refactor only if it becomes awkward.

## Admin UX

Add:

```text
/admin/ideas/suggestions
/admin/ideas/<id>/relationships
```

Review actions:

```text
Accept as new Idea
Merge into existing Idea
Reject
Mark public/private
Link to person/org/place/funding
```

## Acceptance Criteria

- Admin can generate Idea suggestions from at least one existing persona type.
- Suggested Ideas are not public by default.
- Duplicate detection runs before creating a new Idea.
- Accepted Ideas can be linked back to source evidence.
- Public Idea pages can eventually show related people/orgs/places from accepted public-safe relationships.

## Out of Scope

- Fully automatic ontology construction.
- Unreviewed public idea generation.
- Complex graph visualization.

---

# Chunk 5 — Expand Matching Beyond Funding-to-Idea

## Why this matters

Funding-to-Idea matching is a useful first slice, but the original vision requires collaboration hypotheses grounded in known work. That requires matching people, organizations, places, Ideas, funding, and Hub capabilities.

## Build Match Types in This Order

```text
1. person_to_idea
2. organization_to_idea
3. funding_to_person
4. funding_to_organization
5. hub_to_target
6. place_to_idea
```

Keep deterministic candidate generation before LLM scoring.

## Scoring Components

Use explicit sub-scores:

```text
topic_fit
method_fit
hub_capability_fit
funding_fit
recency
evidence_strength
effort_reasonableness
strategic_value
```

Do not collapse effort into value.

```text
A heavy-effort opportunity may still be high-value.
A mild-effort opportunity may still be low-fit.
```

## Admin UX

On each entity detail page, show:

```text
Candidate matches
Accepted matches
Rejected/archived matches
Public-safe matches
Private rationale
```

Add run controls:

```text
Generate matches for this entity
Generate funding matches
Generate Idea matches
Generate Hub-fit matches
```

## Acceptance Criteria

- At least person-to-Idea and funding-to-person matching work.
- Accepted match edges can be reused by collaboration hypotheses.
- Public-safe visibility continues to gate public display.
- Private rationale and score are never shown publicly.
- Staleness is marked when source entity tags/personas/funding fields change.

## Out of Scope

- Fully automated nightly matching.
- Autonomous outreach.
- Graph embedding infrastructure.
- Complex vector search unless already needed.

---

# Chunk 6 — Rich Collaboration Hypotheses

## Why this matters

The app should not merely say “this person matches this funding.” It should generate actionable, evidence-grounded collaboration hypotheses for the Neurotech Hub.

## Build

Upgrade collaboration hypotheses from one-edge summaries to target-centered syntheses.

Input:

```text
target person/org/place
accepted matches
related Ideas
related Funding
Hub capabilities
recent evidence snippets
effort index
relationship context if available
```

Output:

```text
title
hypothesis_summary
why_now
evidence_summary
hub_fit_summary
funding_fit_summary
effort_and_timing
recommended_action
risks_or_unknowns
score_fit
score_timing
score_funding
score_effort
score_relationship
score_total
```

## Admin UX

Add workflow:

```text
Select target → review accepted matches → generate hypothesis → edit/review → mark active/dismissed/contacted
```

Hypothesis categories:

```text
Best now
Funding-aligned
Easy pilot
Strategic heavy lift
Needs relationship-building
```

## Acceptance Criteria

- Hypotheses can use multiple accepted matches.
- Hypotheses include funding and effort when available.
- Admin can edit/dismiss/prioritize.
- Existing `LeadReport` behavior remains intact.
- No public page exposes private hypothesis text.

## Out of Scope

- Sending emails.
- CRM replacement.
- Automatic lead status changes.
- Migrating/deleting existing LeadReports without a separate deliberate migration.

---

# Chunk 7 — Public Explore, Search, and Homepage Refresh

## Why this matters

The public site should feel like a fun, resourceful, exploratory research atlas. Current public pages are useful but still section-specific. The next public layer should help visitors browse across people, orgs, places, Ideas, funding, and latest signals.

## Build

Add:

```text
/explore
/search
```

Homepage refresh:

```text
Idea spotlights
Funding Radar preview
Latest signals with related Idea/Funding chips
Featured places or organizations
Submit URL / request support CTA
```

Explore page sections:

```text
Explore by Idea
Explore by Funding
Explore by Organization
Explore by Place
Explore Latest Signals
```

Search should be simple first:

```text
public people
public organizations
public Ideas
public Funding
public latest content
```

## Reusable Components

Create shared card/chip components for:

```text
EntityCard
IdeaChip
FundingChip
EffortBadge
VisibilityBadge
RelatedEntityList
LatestSignalCard
```

## Public Boundary

Public pages may show:

```text
accepted public-safe relationships
public summaries
tags
effort index
source links
related Ideas/Funding
```

Public pages must not show:

```text
private match scores
private rationale
collaboration hypotheses
outreach recommendations
inferred pain points
unreviewed LLM output
```

## Acceptance Criteria

- `/explore` works without requiring graph visualization.
- `/search` returns grouped public-safe results.
- Homepage exposes Ideas/Funding without overwhelming the current aesthetic.
- Public person/org pages can show related Ideas/Funding only through accepted public-safe edges.
- Existing public pages retain the current visual style.

## Out of Scope

- Interactive graph canvas.
- Personalized recommendations.
- User accounts.
- Public commenting/submission beyond existing intake/request flows.

---

# Chunk 8 — Admin Review Queues

## Why this matters

As soon as LLM suggestions and expanded matching exist, the admin area needs operator visibility. Otherwise useful generated objects will be buried in detail pages.

## Build

Add review queues for:

```text
Imported Funding needing review
Funding fetch/synthesis failures
Generated Idea suggestions
Pending matches
Draft collaboration hypotheses
Public-safe visibility candidates
LLM runs with errors
```

Possible route:

```text
/admin/review
```

Each queue item should show:

```text
object type
title
reason it needs review
created/updated time
source/provider
primary action
secondary actions
```

## Acceptance Criteria

- Admin can see pending generated work in one place.
- Failed LLM/fetch items are visible.
- Review actions update object state.
- Public visibility decisions remain explicit.

## Out of Scope

- Complex Kanban board.
- Multi-user assignment.
- Notifications.

---

## Recommended Next Sprint Order

Use this exact order unless implementation constraints require small swaps:

```text
Sprint 1
  1. Settings page
  2. LLMRun logging
  3. Funding fetch/extract

Sprint 2
  4. Funding synthesis via prompt registry
  5. Effort regeneration from source/synthesis
  6. Funding public-card synthesis

Sprint 3
  7. Idea suggestions from personas/content
  8. Idea duplicate/merge workflow
  9. Manual/public-safe relationship editing

Sprint 4
  10. Expanded matching: person/org/funding
  11. Rich collaboration hypotheses
  12. Admin review queues

Sprint 5
  13. /explore
  14. /search
  15. Homepage refresh
  16. Related cards across public people/org/place pages
```

---

## Guidance to Cursor / Coding Agent

When implementing, always reference the roadmap documents in this order:

```text
1. docs/roadmap_public_site_leads_funding.md
2. docs/implementation_sequence.md or docs/implementation_steps.md
3. docs/funding_model.md
4. docs/effort_index.md
5. docs/idea_model.md
6. docs/matching_and_leads.md
7. docs/public_site_ux.md
8. docs/prompt_specs.md
9. docs/agent_tasks.md
```

Before editing code:

```text
1. Inspect existing admin layout and navigation.
2. Reuse current templates, cards, tables, badges, and route patterns.
3. Maintain the current public-site aesthetic.
4. Avoid introducing a visually separate design system.
5. Prefer small, testable changes.
6. Preserve existing LeadReport behavior.
7. Do not auto-publish LLM output.
8. Do not trigger OpenAI without explicit settings/confirmation.
9. Keep CSV import as a primary funding test path.
```

---

## Definition of Done for the Next Major Milestone

The next major milestone is complete when:

```text
Admin can upload or enter funding links.
Admin can fetch and synthesize funding source text safely.
Admin can see every LLM call and failure.
Funding records can be matched to Ideas, people, and organizations.
Ideas can be suggested from existing evidence and reviewed before publication.
Collaboration hypotheses can be generated from accepted matches.
Public users can explore Ideas, Funding, people, organizations, places, and latest signals through a coherent discovery interface.
Private scores, rationales, hypotheses, and outreach angles remain private.
```

At that point, Synapse will have moved from a curated directory plus deterministic matching into the intended research-intelligence system: a public exploration layer backed by a private collaboration-discovery engine.
