# Synapse Vision Review and Next Steps

## Purpose

This document reviews the current Synapse implementation and defines the next steps needed to reach the original product vision:

> Synapse should become a research opportunity graph for the Neurotech Hub: a system that connects people, organizations, places, ideas, funding, and evidence into public discovery and private collaboration hypotheses.

The recent implementation has moved the app from a basic persona/lead-report system into a broader foundation for research intelligence. The next phase should focus on connecting the pieces into an end-to-end workflow rather than adding many new disconnected pages.

## Current Assessment

The implementation is in a good place. The hardest structural foundations are now present:

- Funding exists as a first-class object.
- Funding CSV import, admin review, public visibility, and bounded source-text fetch exist.
- Effort index exists and is deterministic.
- Ideas exist as first-class public/admin objects.
- Matching models exist.
- Deterministic Funding-to-Idea matching exists.
- Collaboration hypotheses exist, though only in a simple one-match form.
- Public Funding and Ideas pages exist.
- Prompt files, prompt registry, validation, Settings, and `LLMRun` logging scaffolding exist.
- Public/private boundaries are being respected.

The most important gap is that Synapse still does not yet complete the core loop:

```text
Evidence → Synthesis → Ideas → Matches → Collaboration Hypotheses → Public Discovery / Private Action
```

Right now, several parts of that loop exist, but they are not wired together with live synthesis, review queues, relationship expansion, and target-centered hypotheses.

## Strategic Direction

### Prioritize now

```text
1. Wire live LLM execution safely.
2. Use it first for funding synthesis.
3. Add review UI for synthesized outputs.
4. Generate Ideas from existing evidence.
5. Expand matching beyond Funding ↔ Idea.
6. Generate rich collaboration hypotheses from accepted matches.
7. Add central admin review queues.
8. Build public Explore/Search once the graph has enough relationships.
```

### Defer for now

```text
- Complex public graph visualizations
- Fully persistent editable settings
- Automated web crawling
- Autonomous lead generation
- Email/outreach automation
- Vector search infrastructure
- Heavy ontology design
- Major redesign of the public site
```

Those may become useful later, but they are not the next bottleneck.

# Phase 1 — Live LLM Execution Layer

## Goal

Convert the existing prompt registry, validation layer, Settings page, and `LLMRun` model into a real execution pathway.

## Why this is first

Funding synthesis, Idea suggestions, match rationale generation, and collaboration hypotheses all depend on live prompt execution. The app already has the safety/logging scaffolding; now it needs one generic, tested execution path.

## Required work

Add a provider execution wrapper, likely under:

```text
app/llm/providers.py
app/llm/execute.py
app/llm/json_repair.py
```

Every live call should follow this path:

```text
settings/cap check
  → prompt registry render
  → create LLMRun
  → provider call
  → parse JSON
  → validate JSON
  → optional repair
  → complete/fail LLMRun
  → return structured result
```

## Provider policy

```text
Ollama first
OpenAI disabled unless explicitly enabled
OpenAI requires explicit admin action or escalation setting
No automatic public publishing from LLM output
```

## Acceptance criteria

- A test prompt can be executed from an admin-only action or internal test route/service.
- Every prompt call creates an `LLMRun`.
- Failures are visible in Settings or a run detail view.
- JSON validation failures are logged.
- Provider/model/prompt/version/input hash/output hash are stored.
- Settings caps are checked before execution.
- OpenAI cannot be called accidentally.

## Test gates

```bash
pytest tests/test_prompt_registry.py tests/test_prompt_validation.py
pytest tests/test_llm_run.py
pytest tests/test_admin_settings_routes.py
```

Add new tests for:

```text
LLM execution with mock provider
settings caps
provider disabled behavior
JSON validation failure
LLMRun failure logging
```

# Phase 2 — Funding Synthesis Review Loop

## Goal

Make Funding the first real live-LLM workflow.

Funding is the best first target because the app already supports the model, CSV import, admin detail pages, bounded fetch, raw text extraction, effort index, public Funding Radar, and prompt files.

## Required admin actions

On a funding detail page, add explicit buttons:

```text
Synthesize from fetched text
Regenerate public card
Reclassify effort from synthesis
Apply selected fields
Discard synthesis
```

## Synthesis behavior

The LLM should produce a draft object, not overwrite reviewed data immediately.

Recommended pattern:

```text
FundingOpportunity
  existing manually reviewed fields

FundingSynthesisDraft or synthesized_json
  extracted candidate fields
  confidence
  missing information
  field-level suggestions
  llm_run_id
  generated_at
  applied_at nullable
```

A separate draft table is cleaner, but storing a structured draft blob is acceptable for the first implementation if the UI is clear.

## Must preserve manual review

The UI should distinguish:

```text
current value
synthesized value
apply / ignore
```

Manual fields should not be overwritten silently.

## Fields to synthesize

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
confidence
missing_information
```

## Acceptance criteria

- Admin can fetch a URL, extract text, and run synthesis.
- Synthesized fields are shown for review before applying.
- Manual overrides are preserved unless explicitly changed.
- Effort can be regenerated from synthesized text.
- Public summary can be regenerated.
- Failed runs are logged and visible.
- Public pages only show reviewed/public funding.

# Phase 3 — Idea Suggestions From Existing Evidence

## Goal

Move Ideas from manually created objects to evidence-derived research themes.

Ideas are the connective tissue between people, organizations, places, content, funding, and Hub capabilities.

## First sources

Start with:

```text
PersonaSnapshot
ContentItem
```

Then expand to:

```text
organization rollups
building/place rollups
latest curated content
```

## Recommended model

```text
IdeaSuggestion
  id
  source_type
  source_id
  title
  short_description
  public_summary
  tags_json
  aliases_json
  hub_capabilities_json
  evidence_json
  duplicate_candidate_id
  confidence
  status: pending | accepted | rejected | merged
  llm_run_id
  created_at
  reviewed_at
```

## Admin workflow

Add:

```text
/admin/ideas/suggestions
```

Actions:

```text
Generate suggestions from persona
Generate suggestions from content item
Accept as new Idea
Merge into existing Idea
Reject
Edit before accepting
```

## Duplicate handling

Before creating a new public Idea, compare against existing Ideas using:

```text
normalized title
aliases
tag overlap
short description similarity
```

Do deterministic duplicate checks first. LLM duplicate judgment can come later.

## Acceptance criteria

- Admin can generate Idea suggestions from at least one persona.
- Suggestions are private by default.
- Suggestions show source evidence.
- Admin can accept, reject, or merge.
- Accepted Ideas preserve provenance.
- Public Idea pages remain review-gated.

# Phase 4 — Relationship Editing and Match Expansion

## Goal

Turn isolated Funding/Idea links into a broader opportunity graph.

## First add manual relationship editing

Before generating every match automatically, give the admin a way to manually connect entities.

Minimum relationship types:

```text
Idea ↔ Person
Idea ↔ Organization
Idea ↔ Building/Place
Idea ↔ Funding
Funding ↔ Person
Funding ↔ Organization
Hub ↔ Target
```

This can use `MatchEdge` if flexible enough. If `MatchEdge` starts to feel awkward for manually curated relationships, add:

```text
EntityRelationship
  source_type
  source_id
  target_type
  target_id
  relationship_type
  visibility
  status
  rationale
  evidence_json
  created_by: manual | deterministic | llm
```

## Then expand deterministic matching

Recommended order:

```text
1. person_to_idea
2. organization_to_idea
3. funding_to_person
4. funding_to_organization
5. hub_to_target
6. place_to_idea
```

## Candidate scoring

Use sub-scores rather than one opaque score:

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

Effort should remain separate from value.

## LLM use

Use deterministic matching to identify candidates.

Use LLM only for:

```text
top-match rationale
evidence-grounded explanation
Hub relevance summary
public-safe relationship summary
```

## Acceptance criteria

- Admin can manually link Ideas to people/orgs/funding.
- Public-safe visibility is explicit.
- Person-to-Idea matching works deterministically.
- Funding-to-person matching works deterministically.
- Match rationale can be generated for selected top matches.
- Private match rationale is never public.

# Phase 5 — Rich Collaboration Hypotheses

## Goal

Move from simple one-edge hypotheses to target-centered collaboration hypotheses.

This is the private engine that makes Synapse valuable for lead generation.

## Input context

A collaboration hypothesis should synthesize:

```text
target person/org/place
their persona snapshot
recent content evidence
accepted Ideas
accepted Funding matches
Hub capability context
effort index
relationship path if known
private notes if available
```

## Output shape

```text
title
target
hypothesis_summary
why_now
supporting_evidence
Hub fit
funding fit
effort and timing
recommended next action
risks / unknowns
score breakdown
status
```

## Score breakdown

```text
fit_score
timing_score
funding_score
effort_score
relationship_score
strategic_score
total_score
```

## Admin workflow

Add or improve:

```text
Generate hypothesis for target
Review/edit hypothesis
Prioritize
Dismiss
Mark contacted
Mark converted to project
```

## Relationship to existing LeadReport

Do not remove existing `LeadReport`.

Instead add compatibility:

```text
LeadReport can reference CollaborationHypothesis
CollaborationHypothesis can be generated from accepted matches
Existing LeadReport remains functional
```

## Acceptance criteria

- Admin can generate a hypothesis for a person or organization.
- The hypothesis can include multiple accepted matches.
- Funding and effort context are included when available.
- Admin can edit/dismiss/prioritize.
- Existing LeadReport behavior remains unchanged.
- Public site never exposes private hypotheses.

# Phase 6 — Admin Review Queue

## Goal

Create a central operator cockpit.

As LLM suggestions, matches, and hypotheses increase, detail pages alone will not be enough.

## Route

```text
/admin/review
```

## Queues

```text
Funding needing review
Funding fetch failures
Funding synthesis drafts
Generated Idea suggestions
Potential duplicate Ideas
Pending MatchEdges
Public-safe visibility candidates
Draft CollaborationHypotheses
Failed LLMRuns
```

## Recommended UI

Use compact cards or tables with:

```text
object type
title
reason for review
source/provider
created/updated time
primary action
secondary action
```

## Acceptance criteria

- Admin can see all pending generated work from one page.
- Failed LLM/fetch workflows are visible.
- Review actions route to appropriate detail pages.
- Public visibility candidates require explicit approval.

# Phase 7 — Public Atlas Layer

## Goal

Make the public site feel exploratory, useful, and fun.

Do this after the internal graph has enough relationships to expose.

## Build

Add:

```text
/explore
/search
```

Refresh homepage with:

```text
Idea spotlights
Funding Radar preview
Latest signals
Featured people/orgs/places
Request Hub support CTA
Submit URL CTA
```

## Public cross-linking

Add related public-safe Ideas/Funding to:

```text
public person pages
public organization pages
public place/building pages
latest content cards
```

## Reusable components

Create shared public UI pieces:

```text
EntityCard
IdeaChip
FundingChip
EffortBadge
RelatedEntityList
LatestSignalCard
SearchResultGroup
```

## Public privacy rules

Public pages may show:

```text
reviewed public entities
accepted public-safe relationships
public summaries
effort index
tags
source links
```

Public pages must not show:

```text
private match scores
private rationales
collaboration hypotheses
outreach angles
inferred pain points
unreviewed LLM output
```

## Acceptance criteria

- `/explore` provides cross-entity browsing without requiring graph visualization.
- `/search` returns grouped public-safe results.
- Homepage previews Ideas and Funding without disrupting the existing aesthetic.
- People/org pages show related Ideas/Funding only through accepted public-safe relationships.
- Latest cards can show related chips when relationships exist.

# Recommended Sprint Plan

## Sprint A — Make LLM Real, Safely

```text
1. Live LLM execution wrapper
2. Settings/cap enforcement
3. LLMRun integration
4. Mock-provider tests
```

Outcome:

```text
The app can safely execute a prompt and log the result.
```

## Sprint B — Funding Intelligence Loop

```text
1. Funding synthesis from fetched text
2. Synthesis review UI
3. Effort regeneration from synthesis
4. Funding public-card synthesis
```

Outcome:

```text
A funding URL can become a reviewed, public-safe funding card with effort classification.
```

## Sprint C — Idea Generation

```text
1. IdeaSuggestion model
2. Suggest Ideas from PersonaSnapshot
3. Accept/reject/merge UI
4. Idea provenance and duplicate detection
```

Outcome:

```text
Ideas can emerge from the known corpus instead of being manual only.
```

## Sprint D — Opportunity Graph

```text
1. Manual relationship editing
2. Person-to-Idea matching
3. Organization-to-Idea matching
4. Funding-to-person/org matching
5. LLM rationale for selected top matches
```

Outcome:

```text
People, orgs, Ideas, and funding become connected through reviewed relationships.
```

## Sprint E — Collaboration Hypotheses

```text
1. Target-centered hypothesis generation
2. Multi-match synthesis
3. Admin status workflow
4. LeadReport compatibility
```

Outcome:

```text
Synapse produces actionable private collaboration opportunities.
```

## Sprint F — Public Research Atlas

```text
1. /explore
2. /search
3. homepage refresh
4. public cross-links on people/org/place/latest pages
5. reusable cards/chips
```

Outcome:

```text
The public site becomes a discovery layer over the research opportunity graph.
```

# Updated Definition of Done for the Vision

Synapse meets the original vision when:

```text
1. Funding can be imported or fetched from links.
2. Funding pages can be synthesized into reviewed lightweight public cards.
3. Effort is classified simply and visibly.
4. Ideas can be suggested from evidence and reviewed.
5. People, orgs, places, Ideas, and funding can be linked through accepted relationships.
6. Matching expands beyond Funding-to-Idea.
7. Collaboration hypotheses synthesize multiple accepted relationships into actionable private opportunities.
8. Public users can explore Ideas, Funding, people, organizations, places, and latest signals.
9. Admin users can review pending generated objects from a central queue.
10. LLM calls are explicit, logged, bounded, and review-gated.
11. Private scores, rationales, hypotheses, and outreach recommendations never leak publicly.
```

# Immediate Instruction to Coding Agent

Use this as the next concrete implementation directive:

```text
Start with Sprint A.

Implement a live LLM execution wrapper that routes through the existing prompt registry, validates structured output, respects Settings caps/provider policy, and records every call in LLMRun.

Use a mock provider in tests so the full suite does not require Ollama or OpenAI.

Do not wire funding synthesis until the generic LLM execution path is tested.

Do not add public UX pages in this sprint.
```

Once Sprint A is complete, move directly into Funding synthesis because it is the narrowest and most valuable first use of live prompt execution.
