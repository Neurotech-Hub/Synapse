# Synapse Progress Against Vision and Remaining Steps

## Purpose

This document evaluates the current Synapse implementation against the original product vision and outlines the remaining work needed to make the system feel complete, useful, and strategically aligned with the Neurotech Hub.

Original vision:

> Synapse should become a research opportunity graph for the Neurotech Hub: connecting people, organizations, places, ideas, funding, and evidence into public discovery and private collaboration hypotheses.

The current implementation has crossed an important threshold: the core MVP loop now exists. The remaining work is less about proving feasibility and more about improving quality, operator workflow, public discovery, and strategic usefulness.

---

## Current Verdict

Synapse is now past the “foundation” stage.

It has moved from:

```text
ingestion + personas + lead reports
```

toward:

```text
evidence → synthesis → ideas → matches → hypotheses → public discovery / admin review
```

That is a major architectural milestone.

However, the system is not yet at the final vision because several parts of the loop are still shallow:

- synthesis exists, but funding review needs better field-level control
- Ideas can be suggested, but only from persona snapshots
- matching exists, but scoring/rationale are still thin
- collaboration hypotheses exist, but need richer strategic context
- public exploration exists, but the atlas is not yet compelling
- admin review exists, but needs filtering, grouping, prioritization, and better detail views

The next work should focus on quality and usability rather than adding more disconnected objects.

---

# Vision Scorecard

## 1. Funding as a first-class opportunity object

Status: **Mostly achieved**

Implemented:

- Funding model
- Admin CRUD
- CSV import
- duplicate detection
- public/private visibility
- fetch/extract source text
- synthesis draft workflow
- effort index
- public Funding Radar

Remaining:

- field-by-field synthesis review
- public-card regeneration as a distinct action
- high-value/strategic priority flags
- better retry/recovery UX for failed fetches
- better extraction from complex funder pages

Assessment:

Funding is now real enough to support testing and early operation. The next important improvement is making synthesis review feel trustworthy and efficient.

---

## 2. Effort index for funding

Status: **MVP achieved**

Implemented:

- deterministic effort classifier
- effort label
- effort score
- confidence
- rationale
- signals
- manual override
- draft effort use from synthesis

Remaining:

- better integration into funding review
- better connection to collaboration hypotheses
- clearer public explanation/caveat
- optional calibration against real examples

Assessment:

The effort index is appropriately simple. It should stay lightweight. Avoid turning it into a grant-management model.

---

## 3. Ideas as connective tissue

Status: **Partially achieved**

Implemented:

- Idea model
- admin CRUD
- public Idea pages
- Idea suggestions from PersonaSnapshot
- accept/reject/merge workflow
- public-safe Idea/Funding cross-links

Remaining:

- suggestions from ContentItem
- richer duplicate detection
- provenance panels
- relationship editing with people/orgs/places/funding
- bulk review of suggestions

Assessment:

Ideas are structurally present, but not yet central enough. The next step is to make Ideas emerge from evidence and connect them broadly across the graph.

---

## 4. Matching and relationship graph

Status: **MVP achieved, strategically thin**

Implemented:

- MatchRun
- MatchEdge
- manual relationship creation using MatchEdge
- funding-to-Idea matching
- person-to-Idea matching
- organization-to-Idea matching
- funding-to-person matching
- funding-to-organization matching through accepted Idea bridge edges
- public-safe relationship gating

Remaining:

- better scoring quality
- LLM rationale generation for top matches
- Hub-to-target matching
- place/building-to-Idea matching
- match staleness detection
- better match detail pages
- friendlier entity pickers

Assessment:

The relationship graph exists, but it needs stronger explanations and operator tools. The priority should be trust: why does this match exist, how strong is it, and what should I do with it?

---

## 5. Collaboration hypotheses

Status: **MVP achieved, not yet strategic**

Implemented:

- CollaborationHypothesis model
- target-centered generation from accepted match sets
- review queue visibility

Remaining:

- richer hypothesis text using the collaboration prompt
- Hub capability context
- recent public content evidence
- funding and effort context
- edit/prioritize/dismiss/contact workflow
- LeadReport compatibility path
- status history or notes

Assessment:

This is the highest-value private feature. It should become the main admin-facing output of Synapse, not just a generated text artifact.

A strong hypothesis should answer:

```text
Who should the Hub engage?
Why now?
What evidence supports it?
What Idea/funding opportunity connects them?
What Hub capability matters?
How much effort is implied?
What is the recommended next action?
```

---

## 6. Public research atlas

Status: **MVP achieved, needs polish**

Implemented:

- public Funding pages
- public Idea pages
- /explore
- /search
- homepage Idea/Funding spotlights
- public/private safety gates

Remaining:

- richer Explore page
- better search ranking/snippets
- public Places pages
- related Ideas/Funding on public people/org pages
- related chips on Latest cards
- request-support page
- reusable card/chip components

Assessment:

The public site now has the right direction, but not yet the full “fun, resourceful, exploratory” feel. It should become less like separate lists and more like a guided atlas.

---

## 7. LLM safety, settings, and observability

Status: **Strong MVP**

Implemented:

- provider boundary
- execution pipeline
- prompt registry
- settings/cap checks
- JSON parsing and validation
- LLMRun logging
- OpenAI blocked by default
- mock provider tests
- Settings page with recent prompt runs and errors

Remaining:

- operator-facing provider/model selection per task
- persistent editable settings if needed
- explicit OpenAI confirmation UI
- optional JSON repair workflow
- better token/cost estimation
- per-prompt evaluation fixtures

Assessment:

The safety posture is good. Do not loosen it too much. Add quality controls incrementally.

---

# Most Important Remaining Work

## Priority 1 — Improve funding synthesis review

This should be the next implementation focus.

Why:

Funding is the most concrete input for near-term lead generation. If funding synthesis is clunky or untrusted, the rest of the opportunity graph loses value.

Build:

```text
field-by-field synthesis review
apply/ignore per field
highlight changed fields
preserve manual overrides
distinct public-card regeneration action
synthesis confidence display
missing-info display
high-value flag
failed-fetch retry UX
```

Acceptance criteria:

```text
Admin can compare current vs synthesized fields.
Admin can apply selected fields only.
Manual edits are not overwritten silently.
Public card copy can be regenerated separately.
Effort can be updated from synthesis separately.
Failed fetch/synthesis states are easy to recover from.
```

---

## Priority 2 — Add Idea suggestions from ContentItem

Why:

Persona-derived Ideas are useful, but ContentItems are closer to live signals. This lets Ideas emerge from papers, RSS entries, submitted URLs, and public latest items.

Build:

```text
generate IdeaSuggestion from one ContentItem
generate IdeaSuggestion from a selected set of ContentItems
show source evidence
accept/reject/merge
link accepted Idea back to ContentItem evidence
```

Acceptance criteria:

```text
Admin can generate suggestions from ContentItem detail or batch view.
Suggestions show evidence snippets.
Accepted Ideas preserve provenance.
Duplicate detection runs before creation.
No suggestion becomes public without review.
```

---

## Priority 3 — Make relationships easier to create and inspect

Why:

The opportunity graph depends on relationships. If creating/reviewing them is awkward, the graph will remain sparse.

Build:

```text
manual relationship editor
friendly entity picker
relationship detail page
public-safe toggle with explanation
relationship evidence/rationale panel
match status history
```

Acceptance criteria:

```text
Admin can manually link Idea ↔ Person, Idea ↔ Org, Idea ↔ Funding.
Admin can inspect why a match exists.
Admin can mark a relationship public-safe intentionally.
Public pages only show accepted public-safe relationships.
```

---

## Priority 4 — Add LLM rationale generation for selected matches

Why:

Deterministic matching is useful for recall, but operators need explanations. LLM rationale should be used selectively for top matches, not for every candidate.

Build:

```text
Generate rationale for selected match
Use prompt registry and LLMRun
Include evidence snippets
Include confidence and caveats
Store private rationale
Optionally generate public-safe short relationship summary
```

Acceptance criteria:

```text
Admin can generate rationale on a match detail page.
Rationale references available evidence.
Failed/invalid rationale calls are logged.
Private rationale never appears publicly.
Public-safe summary is review-gated.
```

---

## Priority 5 — Upgrade collaboration hypotheses into strategic outputs

Why:

This is the private “lead generation” product. It should become the thing the Hub uses to decide who to engage.

Build:

```text
richer hypothesis prompt use
Hub capability context
recent evidence context
funding + effort context
recommended next action
risks/unknowns
score breakdown
edit/prioritize/dismiss/contact workflow
notes/status history
LeadReport compatibility link
```

Acceptance criteria:

```text
A person/org hypothesis can synthesize multiple accepted relationships.
Funding and effort are included when available.
Hub capability fit is explicit.
Admin can edit and prioritize.
Admin can mark dismissed/contacted/converted.
Existing LeadReport behavior remains intact.
```

---

## Priority 6 — Polish admin review queues

Why:

The system now generates multiple reviewable objects. Operators need one cockpit.

Build:

```text
filter by object type
filter by review reason
sort by priority/recency
show high-value funding
show failed LLM/fetch rows
bulk accept/reject where safe
link to detail pages
```

Acceptance criteria:

```text
Admin can triage all generated work from /admin/review.
Queue counts are visible.
Failed LLM/fetch cases are easy to find.
Bulk actions are available only for low-risk operations.
```

---

## Priority 7 — Make public Explore/Search feel like an atlas

Why:

The public site should be generous, exploratory, and useful. It should show the value of the graph without exposing private lead logic.

Build:

```text
better /explore layout
grouped /search results
Idea spotlights
Funding radar preview
related Ideas/Funding on people/org pages
related chips on Latest cards
public Places pages
request-support page
reusable card/chip components
```

Acceptance criteria:

```text
Visitors can browse by Idea, Funding, Person, Organization, and Place.
Search returns grouped public-safe results.
People/org pages show public-safe related Ideas/Funding.
Latest cards can show related public chips.
Private rationale, scores, and hypotheses remain hidden.
```

---

# Recommended Next Sprint

## Sprint Goal

Make the system more trustworthy and useful for operators by improving review quality around funding, Ideas, matches, and hypotheses.

## Sprint Scope

```text
1. Funding field-by-field synthesis review
2. Public-card regeneration action
3. Idea suggestions from ContentItem
4. Manual relationship editor and relationship detail page
5. LLM rationale generation for selected matches
```

## Why this sprint

This sprint improves the core loop without overreaching:

```text
Evidence → Synthesis → Ideas → Relationships → Match explanations
```

It gives operators better control and makes the generated intelligence more inspectable.

## Defer to next sprint

```text
- public Places pages
- major Explore/Search redesign
- persistent editable settings
- Hub-to-target matching
- advanced score calibration
- LeadReport migration
```

---

# Recommended Next Public Sprint

After the operator workflow improves, move to public discovery:

```text
1. public people/org related Ideas/Funding
2. related chips on Latest cards
3. improved Explore page
4. improved Search snippets and ranking
5. request-support page
6. public Places pages
```

This sequencing ensures the public site has meaningful relationships to expose before polishing the atlas experience.

---

# Risks

## Risk 1 — Too much LLM output, not enough review

Mitigation:

```text
Keep generated objects draft/private by default.
Require explicit review before publication.
Use review queues aggressively.
```

## Risk 2 — Matching becomes noisy

Mitigation:

```text
Use deterministic matching for recall.
Use LLM rationale only on selected candidates.
Expose score components and evidence.
Allow easy rejection/archive.
```

## Risk 3 — Public site leaks private intelligence

Mitigation:

```text
Public pages only use reviewed entities and accepted public-safe relationships.
Never expose private scores, rationale, hypotheses, or outreach language.
Add tests for public filtering.
```

## Risk 4 — Funding metadata becomes too complex

Mitigation:

```text
Keep the funding schema lightweight.
Use source link as authority.
Store synthesis as draft/helpful summary, not canonical truth.
Keep effort simple: mild/moderate/heavy/unknown.
```

---

# Updated Definition of Done

The next major milestone is complete when:

```text
Funding synthesis is reviewable field by field.
Funding public-card copy can be regenerated and reviewed.
Ideas can be suggested from both personas and content items.
Relationships can be manually created, inspected, and marked public-safe.
Selected matches can receive private LLM rationale.
Collaboration hypotheses include Hub capability, evidence, funding, effort, and next action.
Admin review queues support practical triage.
Public pages expose useful cross-links without exposing private intelligence.
```

At that point, Synapse will be beyond MVP and will start feeling like a true research opportunity graph.
