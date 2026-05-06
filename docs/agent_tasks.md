# Agent Task Plan: Public Site, Funding, Ideas, Matching, and Lead Generation

Status: Draft 1  
Owner: Neurotech Hub / Synapse maintainers  
Related docs:

- `docs/roadmap_public_site_leads_funding.md`
- `docs/funding_model.md`
- `docs/effort_index.md`
- `docs/idea_model.md`
- `docs/matching_and_leads.md`
- `docs/public_site_ux.md`
- `docs/prompt_specs.md`

---

## 1. Purpose

This document converts the Synapse roadmap into agent-ready implementation packets.

The goal is to let multiple agents work in parallel without losing the product direction:

> Synapse should become a research opportunity graph for the Neurotech Hub, connecting people, organizations, places, ideas, funding opportunities, evidence, Hub capabilities, and collaboration hypotheses.

The existing Synapse foundation already includes content ingestion, public intake, admin curation, persona snapshots, organization/place rollups, lead reports, geography primitives, public routes, admin routes, and provider-routed LLM calls. This task plan extends that foundation rather than replacing it.

---

## 2. Coordination rules for agents

### 2.1 Default workflow

Each agent should:

1. Read the related docs listed in the task.
2. Inspect the current code before editing.
3. Prefer small migrations and additive models.
4. Avoid breaking existing persona, ingestion, public site, admin, and lead report flows.
5. Add or update tests with every meaningful change.
6. Keep provider routing compatible with existing Ollama/OpenAI patterns.
7. Keep public/private boundaries strict.

### 2.2 Avoid over-normalization

Funding and research intelligence data will be messy. Agents should avoid building brittle schemas that assume all sources provide the same fields.

Prefer:

- a few universal columns
- raw text capture
- synthesized JSON
- admin overrides
- confidence fields
- review state

Avoid:

- mandatory detailed funder-specific metadata
- NIH-only assumptions
- NSF-only assumptions
- grant-management workflows
- full proposal tracking

### 2.3 Public/private rule

Public site may show:

- people, organizations, places, ideas, public-safe summaries
- funding cards
- public tags
- related public entities
- external links
- general Hub capability framing

Public site must not show:

- private lead scores
- inferred pain points
- outreach strategies
- internal prioritization
- private notes
- collaboration hypotheses marked internal
- model uncertainty details unless intentionally surfaced

### 2.4 Provider/cost rule

Use local Ollama by default for broad, repeatable, low-risk tasks:

- first-pass extraction
- tag generation
- effort index classification
- draft summaries
- rough candidate scoring

Use OpenAI selectively for:

- complex funding pages
- malformed local outputs
- high-value opportunities
- final collaboration hypotheses
- polished public copy
- synthesis across many entities

All LLM calls should be cacheable by source hash, prompt version, and model/provider config.

---

## 3. Shared implementation conventions

### 3.1 Naming

Use product-facing language consistently:

| Concept | Preferred term |
|---|---|
| Sales lead | Collaboration hypothesis |
| Grant | Funding opportunity |
| Grant difficulty | Effort index |
| Topic abstraction | Idea |
| Relationship score | Match edge |
| Hub sales pitch | Hub fit |

### 3.2 Suggested package layout

Agents may adjust to match the existing app structure, but the intended package layout is:

```text
app/funding/
  __init__.py
  models.py
  services.py
  extract.py
  synthesize.py
  effort.py
  routes_admin.py
  routes_public.py

app/ideas/
  __init__.py
  models.py
  services.py
  routes_admin.py
  routes_public.py

app/matching/
  __init__.py
  models.py
  services.py
  scoring.py
  candidate_generation.py
  routes_admin.py

app/collaboration/
  __init__.py
  models.py
  services.py
  routes_admin.py
```

If the existing app prefers fewer packages, keep the implementation idiomatic to the current codebase.

### 3.3 Prompt naming

Prompt filenames should be stable and versionable:

```text
prompts/funding_extract.txt
prompts/funding_effort_index.txt
prompts/idea_extract_from_persona.txt
prompts/idea_match_entity.txt
prompts/match_funding_to_entity.txt
prompts/match_entity_to_idea.txt
prompts/collaboration_hypothesis.txt
prompts/public_entity_summary.txt
prompts/public_funding_card.txt
```

### 3.4 Testing style

Each agent should prefer tests that can run without external network or paid API access.

Use fixtures for:

- sample funding HTML
- sample funding text
- sample person persona JSON
- sample organization persona JSON
- sample idea JSON
- sample match edge JSON
- sample collaboration hypothesis JSON

LLM-dependent behavior should be tested through deterministic service boundaries and mocked model responses.

---

# Agent A — Funding Models and Migrations

## Objective

Add the core `FundingOpportunity` data model and persistence layer without implementing full synthesis or matching.

This creates the first durable entity needed for funding-aware public discovery and private lead generation.

## Relevant docs

- `docs/roadmap_public_site_leads_funding.md`
- `docs/funding_model.md`
- `docs/effort_index.md`

## Likely files touched

```text
app/models.py
app/funding/models.py
app/funding/services.py
app/web/admin/routes.py
app/web/public_routes.py
migrations/versions/*.py
tests/test_funding_model.py
tests/test_funding_admin.py
```

Adjust paths to match the current codebase.

## Implementation steps

1. Add `FundingOpportunity` model.
2. Add migration.
3. Add simple service helpers for create/update/archive.
4. Add model-level defaults.
5. Add basic validation helpers.
6. Add admin list/detail placeholders if needed.
7. Add tests for persistence and defaults.

## Suggested fields

```text
id
slug
title
sponsor_name
source_url
source_type
status
visibility
deadline_date
deadline_text
amount_min
amount_max
amount_text
effort_index
effort_score
effort_rationale
summary_public
summary_private
eligibility_summary
topic_tags_json
method_tags_json
raw_text
synthesized_json
confidence
needs_review
created_at
updated_at
reviewed_at
```

## Acceptance criteria

- Funding opportunities can be created manually.
- Funding opportunities can be updated.
- Funding opportunities can be archived.
- Missing amount/deadline fields are allowed.
- `effort_index` supports at least `mild`, `moderate`, `heavy`, and `unknown`.
- `status` supports at least `draft`, `active`, `expired`, and `archived`.
- Model tests pass.
- Existing tests still pass.

## Required tests

- create funding opportunity with minimum fields
- create funding opportunity with rich fields
- update status
- update effort index
- serialize/deserialize JSON fields
- allow unknown deadline
- allow unknown amount

## Out of scope

- URL fetching
- LLM synthesis
- public funding pages
- matching
- collaboration hypotheses

---

# Agent B — Funding Ingestion and Text Extraction

## Objective

Allow an admin to provide a funding URL and store extracted page text for review and later synthesis.

This should be lightweight and resilient across NIH, NSF, foundation, nonprofit, internal, and other pages.

## Relevant docs

- `docs/funding_model.md`
- `docs/prompt_specs.md`

## Likely files touched

```text
app/funding/extract.py
app/funding/services.py
app/web/admin/routes.py
app/templates/admin/funding/*.html
tests/test_funding_extract.py
tests/fixtures/funding_pages/*.html
```

## Implementation steps

1. Add URL fetch helper.
2. Add canonical URL normalization if not already available.
3. Extract page title.
4. Extract readable text.
5. Store raw text on `FundingOpportunity.raw_text`.
6. Store fetch metadata in `synthesized_json` or a dedicated metadata JSON field.
7. Add admin action: “Fetch text from URL.”
8. Add graceful failure messages.

## Recommended extraction behavior

The extractor should return:

```json
{
  "source_url": "",
  "resolved_url": "",
  "title": "",
  "text": "",
  "content_hash": "",
  "fetched_at": "",
  "status_code": 200,
  "error": null
}
```

## Acceptance criteria

- Admin can paste a funding URL.
- App fetches and stores readable text.
- App records content hash.
- App does not fail hard on poor pages.
- App can handle pages with sparse or messy HTML.
- App avoids duplicate fetches when content hash is unchanged.

## Required tests

- clean HTML extraction
- messy HTML extraction
- empty page behavior
- network failure behavior using mocks
- duplicate content hash behavior
- title extraction

## Out of scope

- LLM extraction
- effort index classification
- public pages
- matching

---

# Agent C — Funding Synthesis and Effort Index

## Objective

Convert extracted funding text into a lightweight synthesized funding card, including effort index.

This is where Synapse turns messy funding pages into useful, reviewable intelligence.

## Relevant docs

- `docs/funding_model.md`
- `docs/effort_index.md`
- `docs/prompt_specs.md`

## Likely files touched

```text
app/funding/synthesize.py
app/funding/effort.py
app/ingest/llm_client.py
prompts/funding_extract.txt
prompts/funding_effort_index.txt
tests/test_funding_synthesis.py
tests/test_effort_index.py
```

## Implementation steps

1. Add deterministic heuristic pre-classifier for effort index.
2. Add prompt for funding extraction.
3. Add prompt for effort index if separate from extraction.
4. Add synthesis service.
5. Use Ollama by default.
6. Add OpenAI override/fallback hooks.
7. Validate JSON output.
8. Store synthesized JSON and review flags.
9. Preserve admin overrides.

## Output schema

```json
{
  "title": "",
  "sponsor": "",
  "one_sentence_summary": "",
  "public_summary": "",
  "private_summary": "",
  "who_should_care": [],
  "eligible_entities": [],
  "topic_tags": [],
  "method_tags": [],
  "possible_hub_relevance": [],
  "amount_text": "",
  "deadline_text": "",
  "deadline_date": null,
  "effort_index": "mild|moderate|heavy|unknown",
  "effort_score": 0.0,
  "effort_rationale": "",
  "confidence": 0.0,
  "missing_information": []
}
```

## Effort index guidance

Effort is not value.

A heavy opportunity may still be excellent. The index should represent likely application burden, not whether the opportunity is worth pursuing.

Labels:

```text
mild      small/simple opportunity, short application, limited coordination
moderate  meaningful application, some coordination, foundation/pilot-scale
heavy     large award, complex proposal, institutional coordination, multi-year/multi-PI
unknown   insufficient information
```

## Acceptance criteria

- Funding text can be synthesized into JSON.
- Invalid JSON is handled safely.
- Effort index is assigned with rationale.
- Confidence is stored.
- Admin can override output.
- Re-synthesis does not overwrite explicit admin override unless requested.
- Prompt and provider choices are configurable.

## Required tests

- mild effort fixture
- moderate effort fixture
- heavy effort fixture
- unknown effort fixture
- malformed LLM output
- admin override preserved
- local provider selected by default
- OpenAI fallback path mocked

## Out of scope

- Matching people/orgs to funding
- Public funding pages beyond basic card fields
- Deadline notifications

---

# Agent D — Admin Funding UX

## Objective

Create the admin workflow for adding, reviewing, synthesizing, editing, publishing, archiving, and managing funding opportunities.

## Relevant docs

- `docs/funding_model.md`
- `docs/effort_index.md`
- `docs/public_site_ux.md`

## Likely files touched

```text
app/web/admin/routes.py
app/templates/admin/funding/index.html
app/templates/admin/funding/detail.html
app/templates/admin/funding/form.html
app/templates/admin/funding/review.html
app/funding/services.py
tests/test_admin_funding_routes.py
```

## Implementation steps

1. Add Admin → Funding navigation.
2. Add funding index page.
3. Add create/edit form.
4. Add fetch/synthesize/review actions.
5. Add status and visibility controls.
6. Add effort override.
7. Add needs-review filtering.
8. Add archive action.

## Admin UX requirements

Funding index should show:

- title
- sponsor
- status
- visibility
- deadline
- amount text
- effort index
- confidence
- needs review
- updated date

Funding detail should show:

- source link
- public summary
- private summary
- raw extracted text preview
- synthesized JSON preview
- effort rationale
- admin override controls
- related matches placeholder

## Acceptance criteria

- Admin can add funding manually.
- Admin can fetch from URL.
- Admin can synthesize.
- Admin can edit synthesized fields.
- Admin can mark public/private.
- Admin can archive.
- Admin can filter by active/review/expired.

## Required tests

- admin list route
- create form
- edit form
- archive action
- visibility changes
- review flag behavior
- authorization behavior consistent with existing admin patterns

## Out of scope

- Public funding pages
- Automated scheduled funding scraping
- Matching

---

# Agent E — Ideas Model and Admin UX

## Objective

Add the `Idea` entity as the connective tissue between people, organizations, places, funding, Hub capabilities, and collaboration hypotheses.

## Relevant docs

- `docs/idea_model.md`
- `docs/public_site_ux.md`
- `docs/prompt_specs.md`

## Likely files touched

```text
app/ideas/models.py
app/ideas/services.py
app/web/admin/routes.py
app/templates/admin/ideas/*.html
migrations/versions/*.py
tests/test_idea_model.py
tests/test_admin_ideas.py
```

## Implementation steps

1. Add `Idea` model.
2. Add migration.
3. Add admin CRUD.
4. Add visibility/status fields.
5. Add tag fields.
6. Add Hub capability fields.
7. Add duplicate handling strategy.
8. Add basic relationship placeholders.

## Suggested fields

```text
id
slug
title
short_description
public_summary
private_notes
status
visibility
tags_json
method_tags_json
organism_tags_json
hub_capabilities_json
evidence_json
created_at
updated_at
reviewed_at
```

## Acceptance criteria

- Admin can create/edit/archive ideas.
- Ideas can be public or private.
- Ideas can store tags and Hub capabilities.
- Ideas can be linked later to people/orgs/places/funding via `MatchEdge`.
- Duplicate or near-duplicate ideas can be manually merged or marked related.

## Required tests

- create idea
- edit idea
- archive idea
- JSON tag fields
- slug generation
- visibility behavior

## Out of scope

- Automated idea extraction
- Public idea pages
- Matching

---

# Agent F — Idea Extraction from Personas and Content

## Objective

Generate candidate ideas from existing persona snapshots and content evidence.

This should support admin review, not auto-publish ideas.

## Relevant docs

- `docs/idea_model.md`
- `docs/prompt_specs.md`

## Likely files touched

```text
app/ideas/extract.py
app/ideas/services.py
prompts/idea_extract_from_persona.txt
prompts/idea_match_entity.txt
tests/test_idea_extraction.py
```

## Implementation steps

1. Add idea extraction prompt.
2. Extract candidate ideas from a person persona.
3. Extract candidate ideas from an organization persona.
4. Extract candidate ideas from funding summaries.
5. Add deduplication helper.
6. Store candidates as draft ideas or review suggestions.
7. Add admin review action.

## Suggested output schema

```json
{
  "ideas": [
    {
      "title": "",
      "short_description": "",
      "public_summary": "",
      "tags": [],
      "methods": [],
      "organisms": [],
      "hub_capabilities": [],
      "evidence_summary": "",
      "confidence": 0.0
    }
  ]
}
```

## Acceptance criteria

- Can generate idea candidates from existing personas.
- Candidates are reviewable before becoming public.
- Similar ideas are flagged.
- Existing public ideas are not overwritten without review.
- Provider routing follows local-first policy.

## Required tests

- extract ideas from sample person persona
- extract ideas from sample organization persona
- duplicate detection
- malformed LLM JSON handling
- review candidate persistence

## Out of scope

- Full matching engine
- Collaboration hypotheses
- Public idea pages

---

# Agent G — Matching Engine

## Objective

Add structured, explainable matches between entities.

The matching layer should connect people, organizations, places, ideas, funding opportunities, and Hub capabilities without immediately generating outreach text.

## Relevant docs

- `docs/matching_and_leads.md`
- `docs/funding_model.md`
- `docs/idea_model.md`
- `docs/prompt_specs.md`

## Likely files touched

```text
app/matching/models.py
app/matching/services.py
app/matching/scoring.py
app/matching/candidate_generation.py
app/web/admin/routes.py
app/templates/admin/matching/*.html
migrations/versions/*.py
tests/test_match_edge_model.py
tests/test_matching_scoring.py
```

## Implementation steps

1. Add `MatchEdge` model.
2. Add `MatchRun` model if useful.
3. Add candidate generation services.
4. Add deterministic tag-overlap scoring.
5. Add LLM scoring for selected candidate pairs.
6. Store score breakdown and rationale.
7. Add admin match views.
8. Add accept/reject/hide workflow.

## Suggested `MatchEdge` fields

```text
id
source_type
source_id
target_type
target_id
match_type
score_total
score_breakdown_json
rationale
supporting_evidence_json
status
model_provider
model_name
prompt_version
created_at
updated_at
reviewed_at
```

## Match types

```text
person_to_idea
organization_to_idea
place_to_idea
funding_to_idea
funding_to_person
funding_to_organization
hub_to_person
hub_to_organization
hub_to_funding
```

## Scoring dimensions

```text
topic_fit
method_fit
hub_capability_fit
funding_fit
eligibility_fit
recency
evidence_strength
deadline_urgency
effort_reasonableness
strategic_value
```

## Acceptance criteria

- Match edges can be generated and stored.
- Match scores include breakdowns, not only total score.
- Match rationale is stored.
- Admin can accept/reject/hide matches.
- Matching does not expose private data publicly by default.
- LLM scoring is optional and can be mocked.

## Required tests

- create match edge
- deterministic score calculation
- funding-to-idea match
- person-to-idea match
- admin review state
- LLM scoring output validation

## Out of scope

- Collaboration hypothesis generation
- Outreach email drafting
- Public graph visualizations

---

# Agent H — Collaboration Hypotheses

## Objective

Evolve raw matches into actionable, evidence-grounded collaboration hypotheses for the Neurotech Hub.

This is the private lead-generation layer.

## Relevant docs

- `docs/matching_and_leads.md`
- `docs/prompt_specs.md`
- `docs/roadmap_public_site_leads_funding.md`

## Likely files touched

```text
app/collaboration/models.py
app/collaboration/services.py
app/leads/*
app/web/admin/routes.py
app/templates/admin/collaboration/*.html
prompts/collaboration_hypothesis.txt
prompts/outreach_angle.txt
migrations/versions/*.py
tests/test_collaboration_hypothesis.py
```

## Implementation steps

1. Add `CollaborationHypothesis` model.
2. Add service to generate from accepted/high-scoring matches.
3. Pull supporting evidence from personas, funding summaries, ideas, and Hub corpus.
4. Generate private hypothesis summary.
5. Generate recommended action.
6. Store score breakdown.
7. Add admin review and status workflow.
8. Preserve compatibility with existing `LeadReport` pipeline.

## Suggested fields

```text
id
title
target_type
target_id
idea_id
funding_id
hypothesis_summary
evidence_summary
hub_fit_summary
funding_fit_summary
effort_summary
recommended_action
opening_angle
score_fit
score_timing
score_funding
score_effort
score_relationship
score_total
status
visibility
supporting_match_ids_json
supporting_evidence_json
model_provider
model_name
prompt_version
created_at
updated_at
reviewed_at
```

## Recommended statuses

```text
draft
reviewed
active
contacted
dismissed
archived
```

## Acceptance criteria

- Admin can generate a collaboration hypothesis from selected matches.
- Output includes evidence, Hub fit, funding fit if present, effort summary, and recommended action.
- Admin can review and change status.
- Hypotheses remain private by default.
- Existing lead reports are not broken.

## Required tests

- generate hypothesis from person + idea
- generate hypothesis from person + idea + funding
- generate hypothesis from organization + funding
- missing funding behavior
- status transitions
- OpenAI provider path mocked
- Ollama draft path mocked

## Out of scope

- Sending emails
- CRM integration
- automated contact tracking beyond simple status

---

# Agent I — Public Funding Pages

## Objective

Expose public-safe funding opportunities as useful, lightweight discovery cards.

Public funding should be resourceful without pretending to be a complete grant database.

## Relevant docs

- `docs/public_site_ux.md`
- `docs/funding_model.md`
- `docs/effort_index.md`

## Likely files touched

```text
app/web/public_routes.py
app/funding/routes_public.py
app/templates/public/funding/index.html
app/templates/public/funding/detail.html
app/templates/public/components/funding_card.html
tests/test_public_funding.py
```

## Implementation steps

1. Add public funding index route.
2. Add public funding detail route.
3. Add funding card component.
4. Show only public/active items.
5. Include external source link.
6. Add effort chip.
7. Add tags.
8. Add related ideas placeholder if matching exists.

## Public funding card fields

```text
title
sponsor
deadline text/date
amount text
effort index
public summary
topic tags
method tags
external link
```

## Acceptance criteria

- Public users can browse active funding opportunities.
- Public users can open a detail page.
- Private notes are never shown.
- Draft/private/archived funding is hidden.
- External link is prominent.
- Effort index is simple and visible.

## Required tests

- public active funding appears
- private funding hidden
- draft funding hidden
- archived funding hidden
- private summary not rendered
- external link rendered

## Out of scope

- Public matching explanations
- Grant application guidance
- scraping automation

---

# Agent J — Public Ideas and Research Atlas UX

## Objective

Build the public-facing exploratory layer around ideas, people, organizations, places, funding, and latest content.

This should make Synapse feel like a living research atlas rather than a static directory.

## Relevant docs

- `docs/public_site_ux.md`
- `docs/idea_model.md`
- `docs/matching_and_leads.md`

## Likely files touched

```text
app/web/public_routes.py
app/ideas/routes_public.py
app/templates/public/ideas/index.html
app/templates/public/ideas/detail.html
app/templates/public/components/entity_card.html
app/templates/public/components/idea_card.html
app/templates/public/components/tag_chip.html
app/static/*
tests/test_public_ideas.py
```

## Implementation steps

1. Add public idea index.
2. Add public idea detail page.
3. Add related people/orgs/places/funding sections.
4. Add reusable cards and chips.
5. Add public/private filtering.
6. Add “How the Hub can help” section using public-safe Hub capability summaries.
7. Add search/browse affordances if lightweight.

## Desired public feel

The public site should feel:

- exploratory
- generous
- useful
- fun
- resourceful
- evidence-aware
- not sales-heavy

## Acceptance criteria

- Public users can browse ideas.
- Public users can view idea detail pages.
- Related public-safe entities appear when available.
- Private matches and lead scores are not exposed.
- The UI is useful even before matching is fully populated.

## Required tests

- public idea appears
- private idea hidden
- archived idea hidden
- private notes not rendered
- related public funding appears when linked
- rejected/hidden matches not shown

## Out of scope

- Complex graph visualization
- Full-text search engine
- private collaboration hypotheses

---

# Agent K — Prompt Registry, Provider Routing, and Cost Controls

## Objective

Centralize prompt execution and provider routing for the new funding, idea, matching, and collaboration workflows.

This should extend the current provider-routed LLM architecture without creating one-off model calls scattered across the codebase.

## Relevant docs

- `docs/prompt_specs.md`
- `docs/funding_model.md`
- `docs/matching_and_leads.md`

## Likely files touched

```text
app/ingest/llm_client.py
app/llm/*
app/funding/synthesize.py
app/ideas/extract.py
app/matching/services.py
app/collaboration/services.py
prompts/*.txt
tests/test_prompt_registry.py
tests/test_provider_routing.py
```

## Implementation steps

1. Add prompt registry helper if not present.
2. Add prompt versioning convention.
3. Add structured JSON validation helper.
4. Add JSON repair or safe failure behavior.
5. Add provider selection config.
6. Add cost/token logging hooks where possible.
7. Add cache keys based on content hash + prompt version + provider + model.
8. Add tests with mocked model responses.

## Provider routing defaults

```text
funding extraction: Ollama first
funding effort index: Ollama first
idea extraction: Ollama first
candidate matching: deterministic + Ollama
final collaboration hypothesis: OpenAI preferred, Ollama allowed for draft
public polished summary: OpenAI optional, Ollama acceptable for drafts
```

## Acceptance criteria

- New prompts can be added without custom provider code every time.
- LLM outputs are validated before persistence.
- Failed outputs produce reviewable errors, not app crashes.
- Provider routing is configurable by environment.
- Cached results avoid repeated paid calls.

## Required tests

- load prompt by name
- missing prompt behavior
- provider selected by task
- malformed JSON behavior
- cached response behavior
- OpenAI fallback mocked
- Ollama fallback mocked

## Out of scope

- Prompt quality evaluation dataset beyond simple fixtures
- Full tracing dashboard
- live API integration tests by default

---

# Agent L — Search, Browse, and Discovery UI

## Objective

Create simple discovery affordances across public entities without requiring a full search infrastructure on day one.

## Relevant docs

- `docs/public_site_ux.md`
- `docs/idea_model.md`
- `docs/funding_model.md`

## Likely files touched

```text
app/web/public_routes.py
app/search/*
app/templates/public/search.html
app/templates/public/components/search_box.html
tests/test_public_search.py
```

## Implementation steps

1. Add lightweight public search route.
2. Search public people/orgs/places/ideas/funding by title, summary, and tags.
3. Add filter chips by entity type.
4. Add empty-state copy.
5. Add public/private filtering.
6. Keep implementation SQL/simple unless existing retrieval layer supports better.

## Acceptance criteria

- Public users can search across public-safe entities.
- Search does not expose private notes or private entities.
- Results are grouped or labeled by entity type.
- Search works before embeddings are added.

## Required tests

- search public idea
- search public funding
- private item hidden
- archived item hidden
- empty search behavior

## Out of scope

- embeddings
- semantic ranking
- external search service
- autocomplete unless trivial

---

# Agent M — Tests, Fixtures, and Evaluation Harness

## Objective

Create shared fixtures and validation tests so future agents can safely modify prompts, models, and scoring.

## Relevant docs

- all roadmap/spec docs

## Likely files touched

```text
tests/fixtures/funding_pages/*.html
tests/fixtures/funding_synthesis/*.json
tests/fixtures/personas/*.json
tests/fixtures/ideas/*.json
tests/fixtures/matches/*.json
tests/fixtures/collaboration/*.json
tests/conftest.py
tests/test_*.py
```

## Implementation steps

1. Add representative funding fixtures.
2. Add persona fixtures.
3. Add idea fixtures.
4. Add match fixtures.
5. Add collaboration hypothesis fixtures.
6. Add schema validation tests.
7. Add prompt-output validation tests using mocked responses.

## Acceptance criteria

- Agents can test without live web or live LLM access.
- Common schemas have fixtures.
- Prompt outputs have validation tests.
- Matching score calculations have deterministic tests.
- Public/private boundary tests exist.

## Required tests

- fixture load tests
- JSON schema validation tests
- public/private rendering tests
- model migration smoke tests

## Out of scope

- full live model evaluation
- browser-based visual regression unless already present

---

# Agent N — Documentation and Developer Handoff

## Objective

Keep repo documentation aligned with the implementation as agents complete work.

## Relevant docs

- `README.md`
- all new roadmap/spec docs

## Likely files touched

```text
README.md
docs/roadmap_public_site_leads_funding.md
docs/funding_model.md
docs/effort_index.md
docs/idea_model.md
docs/matching_and_leads.md
docs/public_site_ux.md
docs/prompt_specs.md
docs/agent_tasks.md
docs/implementation_sequence.md
```

## Implementation steps

1. Update README only after features exist.
2. Keep roadmap docs clear about draft vs implemented status.
3. Add setup notes for new env vars.
4. Add admin workflow notes.
5. Add public site feature notes.
6. Document provider-routing behavior.
7. Document testing commands.

## Acceptance criteria

- Docs match implemented behavior.
- New env vars are listed.
- New admin workflows are described.
- Public/private boundary is described.
- Feature status is clear.

## Required tests

Not applicable, but documentation should be reviewed alongside code changes.

## Out of scope

- marketing copy polishing
- long-form public launch article

---

## 4. Suggested parallelization

### Work that can start immediately

```text
Agent A — Funding models and migrations
Agent K — Prompt/provider infrastructure
Agent M — Tests and fixtures
Agent N — Documentation shell
```

### Work that depends on Agent A

```text
Agent B — Funding ingestion
Agent C — Funding synthesis and effort index
Agent D — Admin funding UX
Agent I — Public funding pages
```

### Work that can start after basic funding exists

```text
Agent E — Ideas model and admin UX
Agent F — Idea extraction
```

### Work that depends on Funding + Ideas

```text
Agent G — Matching engine
Agent H — Collaboration hypotheses
Agent J — Public research atlas UX
Agent L — Search and discovery
```

---

## 5. Suggested milestone grouping

## Milestone 1 — Funding Foundation

Agents:

- A
- B
- C
- D
- K
- M

Deliverable:

- Admin can add a funding URL, fetch text, synthesize a public-safe funding card, classify effort, review, and publish/archive.

## Milestone 2 — Public Funding Radar

Agents:

- I
- L partial
- N

Deliverable:

- Public users can browse useful funding cards with effort index and external links.

## Milestone 3 — Ideas Layer

Agents:

- E
- F
- J partial
- M

Deliverable:

- Admin can create/review ideas; public users can explore public ideas.

## Milestone 4 — Matching Engine

Agents:

- G
- K
- M

Deliverable:

- Admin can generate and review match edges among funding, ideas, people, organizations, places, and Hub capabilities.

## Milestone 5 — Collaboration Hypotheses

Agents:

- H
- G
- K
- N

Deliverable:

- Admin can generate evidence-grounded collaboration hypotheses from selected matches.

## Milestone 6 — Research Atlas Public Experience

Agents:

- J
- L
- I
- N

Deliverable:

- Public site feels exploratory, resourceful, and coherent across people, organizations, places, ideas, funding, and latest content.

---

## 6. Global acceptance criteria

The full roadmap is successful when:

- Funding opportunities are first-class entities.
- Effort index is visible and simple.
- Funding metadata is lightweight and robust to messy sources.
- Ideas connect people, organizations, places, funding, and Hub capabilities.
- Matches are explainable and reviewable.
- Collaboration hypotheses are private, actionable, and evidence-grounded.
- Public pages are useful without exposing internal lead logic.
- Ollama handles broad local work.
- OpenAI is used selectively for higher-value synthesis.
- Tests cover public/private boundaries and core model behavior.
- Existing Synapse ingestion, persona, admin, and public flows remain functional.

---

## 7. Non-goals for the current phase

Do not build these yet unless explicitly requested:

- full CRM
- automated email outreach
- full grant management system
- proposal calendar management
- full semantic vector search
- browser graph visualization requiring major frontend complexity
- multi-tenant SaaS behavior
- public API
- complex funder-specific schemas
- payment or billing features

---

## 8. Recommended next document

After this file, create:

```text
docs/implementation_sequence.md
```

That document should define the safest build order, dependency graph, migration order, and incremental acceptance checkpoints.
