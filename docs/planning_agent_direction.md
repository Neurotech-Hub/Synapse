# Planning Agent Direction: Synapse Public Site, Funding, and Lead Generation

## Execution shell

Quick runbook for implementation agents. Full rationale and phase detail appear below.

### Primary guides (in `docs/`)

1. [roadmap_public_site_leads_funding.md](roadmap_public_site_leads_funding.md)
2. [implementation_sequence.md](implementation_sequence.md)

Only `implementation_sequence.md` exists in this repo today (there is no `implementation_steps.md`). Use it as the source of truth for dependency sequencing.

### Phase order

1. Funding model — [funding_model.md](funding_model.md)
2. Effort index — [effort_index.md](effort_index.md)
3. Idea model — [idea_model.md](idea_model.md)
4. Matching and leads — [matching_and_leads.md](matching_and_leads.md)
5. Public site UX — [public_site_ux.md](public_site_ux.md)
6. Prompt specs — [prompt_specs.md](prompt_specs.md)
7. Agent tasks — [agent_tasks.md](agent_tasks.md)

### Sample CSV (manual import / dev)

Use [../data/funding_opportunities_sample.csv](../data/funding_opportunities_sample.csv) for local testing until a committed copy exists under `tests/fixtures/` (see [Suggested synthetic CSV test file](#suggested-synthetic-csv-test-file)).

### Start here

Begin **Phase 1** using [funding_model.md](funding_model.md). First milestone exit criteria: [Acceptance criteria for the first implementation milestone](#acceptance-criteria-for-the-first-implementation-milestone).

## Purpose

Use this document as the operating direction for planning and sequencing the next Synapse implementation phase. The goal is to evolve Synapse from a research-intelligence curation app into a public-facing research atlas and private lead-generation system for the Neurotech Hub.

The implementation should preserve the current application architecture and visual identity while adding new entities, admin workflows, funding ingestion, matching, and public exploration features in controlled phases.

## Primary guiding documents

The planning and implementation agents should treat the following as the primary design corpus (all in `docs/`):

1. [`roadmap_public_site_leads_funding.md`](roadmap_public_site_leads_funding.md)
2. [`implementation_sequence.md`](implementation_sequence.md)

Only `implementation_sequence.md` exists in this repository today; there is no `implementation_steps.md`. Treat the sequence file as the source of truth for dependency sequencing. If both filenames appear in the future, reconcile them or standardize on one before implementation begins.

## Phase execution order

Execute the phase-specific documents in this order:

1. `@funding_model.md`
2. `@effort_index.md`
3. `@idea_model.md`
4. `@matching_and_leads.md`
5. `@public_site_ux.md`
6. `@prompt_specs.md`
7. `@docs/agent_tasks.md` or `@agent_tasks.md`

Each phase should explicitly reference the roadmap and implementation sequence as the guiding documents, then execute only the scope of its assigned phase.

## Global implementation principles

### 1. Preserve current app organization

Do not redesign Synapse from scratch. Extend the existing structure.

Preserve the current separation between:

- public routes and templates
- admin routes and templates
- ingestion services
- identity/persona services
- lead-report services
- prompt files
- migrations
- tests

New modules should fit naturally into the existing Flask/SQLAlchemy/Alembic architecture.

### 2. Preserve the current website aesthetic

The planning agent did not have visibility into the current website design. Implementation agents must inspect the existing public and admin templates, CSS, components, spacing, card styles, navigation patterns, typography, and layout before introducing new UI.

New features should feel like native Synapse features, not a separate product bolted on.

Public pages should be exploratory, generous, and polished.

Admin pages should be dense enough to be useful, but not visually chaotic.

### 3. Admin UX should prioritize object visibility

The admin area should provide clear visibility into all major objects/entities:

- people
- organizations
- buildings/places
- sources
- content items
- persona snapshots
- funding opportunities
- ideas
- match edges
- collaboration hypotheses / lead hypotheses
- prompt runs / LLM calls where appropriate

For each major object, provide basic CRUD or the closest safe equivalent:

- create
- read/detail
- update/edit
- archive/delete where appropriate
- rebuild/regenerate when LLM-derived
- review/approve when imported or synthesized

Avoid hiding important objects behind only generated reports.

### 4. Add a Settings area for safeguards and provider controls

If implementation introduces safeguards, recursion limits, provider choices, call caps, prompt settings, or cost-sensitive behavior, expose these in a new or expanded Admin Settings area.

Settings should cover items such as:

- default LLM provider by task
- Ollama/OpenAI fallback behavior
- maximum prompt characters
- maximum batch size
- maximum match candidates per run
- maximum recursive rebuild depth
- whether public web search is enabled
- whether OpenAI calls require explicit admin confirmation
- whether funding imports auto-synthesize or require manual action
- stale/rebuild thresholds
- feature flags for public funding, ideas, and matching

Do not bury these only in environment variables if they affect normal operator behavior. Environment variables may remain the deployment default, but admin-visible configuration should be added where useful.

### 5. Avoid uncontrolled recursion and runaway LLM loops

Any LLM-powered rebuild, synthesis, matching, or report generation must have clear bounds.

Required safeguards:

- explicit job/run records for batch operations
- content hash or input fingerprint before regeneration
- maximum candidate limits
- maximum prompt character limits
- maximum retry count
- no automatic infinite rebuild chains
- no public-triggered expensive LLM calls without rate limiting and review
- no automatic OpenAI escalation unless configured
- human review state for imported/synthesized funding records

Generated outputs should be cached and only regenerated when the underlying input changes or an admin explicitly requests it.

### 6. Funding ingestion starts with CSV upload

For the first implementation pass, assume funding opportunities are collected externally and uploaded as a CSV through the backend/admin interface.

Do not start with general web scraping as the primary workflow.

The MVP workflow should be:

1. Admin uploads a CSV of funding opportunities.
2. Backend validates rows and reports errors before commit.
3. Backend imports valid rows into `FundingOpportunity` records.
4. Admin reviews imported records.
5. Admin can run synthesis/rebuild on selected rows.
6. Synthesized fields and effort index are stored for review.
7. Reviewed records can be made public if appropriate.

Later phases may add:

- fetch from URL
- scrape page text
- synthesize from funding page content
- public web search
- RSS-based funding monitoring

But CSV upload should be the first reliable ingestion path.

### 7. Funding metadata should stay intentionally lightweight

Funding links come from NIH, NSF, foundations, nonprofits, internal seed mechanisms, private philanthropy, and other heterogeneous sources. They will not provide consistent structured metadata.

Do not overfit the schema to a single funder.

Prefer:

- source URL
- title
- sponsor
- deadline text/date if available
- amount text and optional min/max
- lightweight tags
- public summary
- private notes
- effort index
- synthesis JSON blob
- raw imported text/notes

Avoid requiring detailed fields that will be missing for many opportunities.

### 8. Effort index is required but should stay simple

Every funding opportunity should have an effort index:

- `mild`
- `moderate`
- `heavy`
- `unknown`

There is no `none` or `no_effort` class.

The index may be based partly on award amount, but should also consider:

- application complexity
- mechanism type
- team/collaboration burden
- budget size
- duration
- required institutional involvement
- proposal format if known
- confidence in the available evidence

Effort should not be treated as a negative score by itself. A heavy opportunity can still be highly strategic.

### 9. Maintain public/private boundary

Public site may show:

- public funding cards
- public ideas
- public people/org/place pages
- related ideas
- related funding
- public summaries
- source links

Admin-only views should contain:

- lead scores
- inferred pain points
- private outreach strategy
- internal Hub fit analysis
- rejected matches
- score breakdowns
- OpenAI/Ollama run diagnostics
- private notes

Do not expose private lead-generation logic on the public site.

### 10. Provider and cost policy

Default approach:

- Use Ollama for routine extraction, tagging, draft synthesis, and local iteration.
- Use OpenAI for high-value synthesis, complex/failed local extraction, final collaboration hypotheses, and polished public summaries when configured.
- Make OpenAI usage visible and bounded.
- Cache all generated outputs by input fingerprint.

Agents should respect existing Synapse provider-routing patterns where possible.

## CSV funding import requirements

The funding CSV importer should support a minimal, forgiving schema.

Recommended columns:

```csv
external_id,title,sponsor_name,source_url,source_type,status,visibility,deadline_date,deadline_text,amount_min,amount_max,amount_text,mechanism,effort_index_override,topic_tags,method_tags,eligibility_summary,notes_private,raw_text
```

Required fields for import:

- `title`
- `source_url` or `external_id`

Recommended fields:

- `sponsor_name`
- `deadline_date` or `deadline_text`
- `amount_text`
- `topic_tags`
- `notes_private`

Import behavior:

- Trim whitespace.
- Normalize blank values to null.
- Parse tags from semicolon-delimited strings.
- Validate URLs if present.
- Validate `effort_index_override` against allowed labels.
- Validate `status` against allowed labels.
- Validate `visibility` against allowed labels.
- Do dry-run validation before committing.
- Detect duplicates by `external_id` first, then normalized `source_url`.
- Provide row-level error messages.
- Support update-on-duplicate only if the admin explicitly chooses that behavior.

## Suggested synthetic CSV test file

Create and commit a synthetic test CSV for local development, fixtures, and manual admin testing.

Suggested path:

```text
tests/fixtures/funding_opportunities_sample.csv
```

A working synthetic sample for manual import and development lives at [`data/funding_opportunities_sample.csv`](../data/funding_opportunities_sample.csv) until Phase 1 adds a committed fixture at the path above.

The test file should include:

- a mild seed-style opportunity
- a moderate foundation-style opportunity
- a heavy center-style opportunity
- an unknown/incomplete opportunity
- rows with tags
- rows with amount ranges
- rows with deadline text but no parsed date
- at least one row with a duplicate URL for duplicate detection testing
- at least one intentionally imperfect row in a separate invalid fixture

Do not use real funding claims in the test fixture unless they are deliberately verified and kept current. Prefer synthetic examples for stable tests.

## Phase-specific instructions

### Phase 1 — Funding model

Primary doc: `@funding_model.md`

Implement:

- `FundingOpportunity` model
- migrations
- admin funding list/detail/edit pages
- CSV upload/import workflow
- dry-run validation
- row-level import errors
- duplicate detection
- public/private visibility field
- basic public funding cards only if feature flag is enabled

Do not implement sophisticated matching yet.

### Phase 2 — Effort index

Primary doc: `@effort_index.md`

Implement:

- effort labels
- manual override
- heuristic classifier
- optional LLM classifier
- effort rationale
- confidence field
- admin rebuild/regenerate action
- display badges in admin/public cards

Do not let effort collapse the full lead score. It is one dimension.

### Phase 3 — Idea model

Primary doc: `@idea_model.md`

Implement:

- `Idea` model
- admin CRUD
- public idea pages behind feature flag
- tags/capabilities
- links to people/orgs/places/funding where supported
- manual idea creation first
- LLM-assisted extraction later if bounded

### Phase 4 — Matching and leads

Primary doc: `@matching_and_leads.md`

Implement:

- `MatchEdge`
- match runs/jobs
- candidate generation
- bounded scoring
- explainable rationale
- `CollaborationHypothesis`
- admin review/accept/reject workflow

Keep existing `LeadReport` behavior functional during transition.

### Phase 5 — Public site UX

Primary doc: `@public_site_ux.md`

Implement:

- public funding pages/cards
- public idea pages
- related entity cards
- exploratory navigation
- atlas-like discovery patterns
- public/private filtering
- feature flags

Preserve current aesthetic. Inspect existing templates before editing.

### Phase 6 — Prompt specs

Primary doc: `@prompt_specs.md`

Implement or consolidate:

- prompt registry
- funding extraction prompt
- effort classification prompt
- idea extraction prompt
- matching prompt
- collaboration hypothesis prompt
- public summary prompt
- JSON validation/repair
- provider routing
- prompt versioning
- token/cost logging where practical

Prompt specs may need to be referenced earlier by each phase, but this phase should consolidate and standardize them.

### Phase 7 — Agent tasks

Primary doc: `@docs/agent_tasks.md` or `@agent_tasks.md`

Use this phase to reconcile implementation work packets after the architecture and core implementation decisions are stable.

Update agent tasks to reflect what was actually implemented, what was deferred, and what remains blocked.

## Acceptance criteria for the first implementation milestone

The first milestone is complete when:

- `FundingOpportunity` exists with migrations.
- Admin can upload a CSV.
- CSV import supports dry-run validation.
- Valid rows can be committed.
- Invalid rows produce row-level errors.
- Duplicate rows are detected.
- Admin can view/edit/archive funding records.
- Funding records have an effort index field.
- A synthetic sample CSV exists for tests/manual import.
- Existing public/admin pages still render normally.
- Existing tests still pass.
- New import/model tests are added.

## Final instruction to agents

Implement incrementally. Keep the app usable after each phase. Prefer small, reviewable migrations and UI additions over large rewrites. Use the roadmap for direction, but let the existing Synapse codebase determine final organization and style.
