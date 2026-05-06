# Idea Model Spec

## Purpose

This document defines the **Idea** layer for Synapse.

Ideas are the connective tissue between people, organizations, places, funding, content evidence, Hub capabilities, and future collaboration hypotheses. They allow Synapse to become more than a directory of entities or a list of funding opportunities. They let the public site become exploratory and let the private lead pipeline reason about meaningful scientific and technical opportunities.

An Idea is not necessarily a formal project. It can be a research theme, technical bottleneck, methodological cluster, buildable concept, translational opportunity, or emerging area of interest.

Examples:

- Automated home-cage behavior
- Closed-loop behavioral systems
- Chronic electrophysiology tooling
- Wireless neural interfaces
- Computational ethology
- Miniaturized behavioral sensors
- Long-duration home-cage monitoring
- Implantable stimulation devices
- Low-power neuroscience data loggers
- Multimodal behavioral phenotyping
- AI-assisted experiment monitoring
- Modular reward-delivery systems

The goal is to make Synapse capable of answering:

> What ideas are emerging, who is near them, where are they happening, what funding could support them, and how could the Neurotech Hub help?

---

## Design principles

1. **Ideas should be useful, not exhaustive.**
   Synapse does not need a perfect ontology of neuroscience. It needs practical concepts that help public users explore and help Hub operators identify collaboration opportunities.

2. **Ideas should be evidence-linked.**
   An Idea can be manually curated, LLM-suggested, or extracted from personas, but important associations should be grounded in evidence from content items, source excerpts, or persona snapshots.

3. **Ideas should bridge public and private use cases.**
   Public Idea pages should feel generous and educational. Private Idea views can include lead logic, Hub-fit analysis, and outreach opportunities.

4. **Ideas should be editable.**
   LLM-generated ideas will be noisy. Admin review, merging, renaming, hiding, and status control are required.

5. **Ideas should support multiple granularity levels.**
   `Neural interfaces` is broad. `Wireless head-mounted miniscope synchronization` is narrow. Both can be useful, but the system should distinguish broad themes from specific buildable concepts.

6. **Ideas should not require perfect taxonomy upfront.**
   Start with tags, aliases, and related ideas before building rigid parent-child ontology.

---

## Scope

This spec covers:

- `Idea` data model.
- Idea status and visibility.
- Idea extraction from personas/content.
- Manual idea creation and curation.
- Public idea pages.
- Admin idea management.
- Idea-to-entity matching preparation.
- Prompt and provider strategy.
- Acceptance criteria and tests.

This spec does **not** cover:

- Full matching engine implementation.
- Lead/collaboration hypothesis generation.
- Funding-to-idea scoring details.
- Public map/graph visualization implementation.
- Automated background scheduling.

Those are covered in later documents.

---

## Core concept

### What counts as an Idea?

An Idea should usually satisfy at least one of these:

1. It describes a recognizable research or technical theme.
2. It connects multiple people, organizations, content items, or funding opportunities.
3. It represents a possible Hub-supported build, service, method, or collaboration.
4. It is useful as a public exploratory page.
5. It helps explain why an entity is relevant to the Hub.

### What should not become an Idea?

Avoid creating Ideas for:

- Single paper titles with no broader reuse.
- One-off generic keywords such as `biology`, `science`, or `technology`.
- Person-specific claims that only describe one researcher.
- Funding mechanism names, unless they represent a broader funding theme.
- Administrative categories with no research meaning.

---

## Idea types

Recommended initial values:

```text
research_theme
technical_capability
buildable_concept
method_cluster
funding_theme
strategic_area
public_resource_topic
unknown
```

### `research_theme`

A scientific area or question.

Examples:

- Sleep and circuit function
- Motivated behavior
- Neurodegeneration biomarkers
- Social behavior and neural computation

### `technical_capability`

A tool, service, or technical method area.

Examples:

- Chronic electrophysiology
- Wireless data logging
- Low-power embedded sensing
- Closed-loop stimulation

### `buildable_concept`

A concrete thing the Hub could help design, prototype, validate, or deploy.

Examples:

- Modular home-cage foraging platform
- Head-mounted environmental sensor logger
- Low-cost behavioral event counter
- Automated reward delivery module

### `method_cluster`

A group of related methods or experimental workflows.

Examples:

- Home-cage behavioral phenotyping
- Multimodal behavioral monitoring
- In vivo recording plus closed-loop perturbation

### `funding_theme`

A topic useful for grouping funding opportunities.

Examples:

- Early-stage technology development
- Shared instrumentation
- Team science
- Pilot awards

### `strategic_area`

A Hub-relevant priority area.

Examples:

- Scalable behavioral infrastructure
- Open-source neuroscience hardware
- Translation from prototype to deployable platform

### `public_resource_topic`

A topic useful for public resource pages even if it is not immediately lead-oriented.

Examples:

- How to choose a behavioral sensor
- Data visibility for long-running experiments
- Funding mechanisms for neurotechnology pilots

---

## Recommended data model

### `Idea`

```python
class Idea(db.Model):
    __tablename__ = "ideas"

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(240), nullable=False)
    slug = db.Column(db.String(260), nullable=True, unique=True, index=True)

    idea_type = db.Column(db.String(50), nullable=False, default="unknown")
    status = db.Column(db.String(40), nullable=False, default="draft")
    is_public = db.Column(db.Boolean, nullable=False, default=False)

    short_description = db.Column(db.String(500), nullable=True)
    public_summary = db.Column(db.Text, nullable=True)
    private_summary = db.Column(db.Text, nullable=True)

    hub_relevance = db.Column(db.Text, nullable=True)
    buildable_angle = db.Column(db.Text, nullable=True)
    funding_angle = db.Column(db.Text, nullable=True)

    tags_json = db.Column(db.JSON, nullable=True)
    aliases_json = db.Column(db.JSON, nullable=True)
    hub_capabilities_json = db.Column(db.JSON, nullable=True)
    evidence_refs_json = db.Column(db.JSON, nullable=True)
    synthesized_json = db.Column(db.JSON, nullable=True)

    confidence_score = db.Column(db.Float, nullable=True)
    quality_flags_json = db.Column(db.JSON, nullable=True)

    created_by = db.Column(db.String(80), nullable=True)
    created_via = db.Column(db.String(40), nullable=False, default="manual")

    generated_at = db.Column(db.DateTime, nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
```

### Field notes

| Field | Notes |
|---|---|
| `title` | Human-readable canonical name. |
| `slug` | Public URL identifier. |
| `idea_type` | Lightweight category; not a rigid ontology. |
| `status` | `draft`, `review`, `public`, `private`, `archived`, `hidden`, `merged`. |
| `is_public` | Explicit public visibility flag. |
| `short_description` | One-line definition. |
| `public_summary` | Public-facing explanation. |
| `private_summary` | Internal reasoning, strategy, or Hub-specific notes. |
| `hub_relevance` | Why the Hub might care. |
| `buildable_angle` | What could potentially be built, prototyped, or supported. |
| `funding_angle` | What kinds of funding might support this area. |
| `tags_json` | Simple searchable terms. |
| `aliases_json` | Alternate names and related phrases. |
| `hub_capabilities_json` | Relevant Hub capabilities. |
| `evidence_refs_json` | Pointers to content items, personas, source URLs, or manual notes. |
| `synthesized_json` | Full LLM output for traceability. |
| `confidence_score` | How confident the system is that this is a useful idea. |
| `quality_flags_json` | `too_broad`, `too_narrow`, `duplicate_possible`, `needs_review`, etc. |
| `created_via` | `manual`, `persona_extract`, `content_extract`, `funding_extract`, `admin_seed`, `imported`. |

---

## Optional relationship models

The matching engine will later add generalized `MatchEdge` records, but the Idea MVP may benefit from explicit join tables for admin curation.

### `IdeaEntityLink`

```python
class IdeaEntityLink(db.Model):
    __tablename__ = "idea_entity_links"

    id = db.Column(db.Integer, primary_key=True)

    idea_id = db.Column(db.Integer, db.ForeignKey("ideas.id"), nullable=False, index=True)

    entity_type = db.Column(db.String(40), nullable=False)  # person, organization, building, funding
    entity_id = db.Column(db.Integer, nullable=False, index=True)

    link_type = db.Column(db.String(60), nullable=False, default="related")
    score = db.Column(db.Float, nullable=True)
    rationale = db.Column(db.Text, nullable=True)
    evidence_refs_json = db.Column(db.JSON, nullable=True)

    source = db.Column(db.String(40), nullable=False, default="manual")
    status = db.Column(db.String(40), nullable=False, default="suggested")

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime, nullable=True)
```

Recommended `entity_type` values:

```text
person
organization
building
region
funding
content_item
hub_capability
```

Recommended `link_type` values:

```text
works_on
uses_method
needs_capability
could_fund
could_support
located_near
affiliated_with
public_related
private_lead_signal
```

Recommended `status` values:

```text
suggested
accepted
rejected
hidden
```

### Why use a join table before full `MatchEdge`?

It allows early manual curation and public page rendering without waiting for the generalized scoring system. Later, accepted `IdeaEntityLink` rows can be migrated into or supplemented by `MatchEdge` records.

---

## Public/private boundary

### Public-safe Idea content

Public Idea pages may show:

- Clear explanation of the idea.
- Related public people, organizations, places, and funding.
- Public evidence snippets.
- Hub capabilities in broad terms.
- External links.
- Educational framing.

### Private-only Idea content

Admin views may show:

- Lead potential.
- Inferred technical pain points.
- Strategic value to the Hub.
- Suggested outreach angles.
- Private scoring.
- Internal notes.
- Unreviewed LLM-generated connections.

### Rule of thumb

The public site should say:

> This idea is active, interesting, and connected to these public resources.

The admin site may say:

> This idea suggests a high-value collaboration opportunity with these targets.

---

## Admin workflows

### 1. Manual idea creation

Admin can create an Idea directly:

Required:

- title
- idea type
- short description

Optional:

- public summary
- private summary
- Hub relevance
- tags
- aliases
- related people/orgs/places/funding

### 2. Idea suggestion from persona

On a person/org/place persona page:

Button:

```text
Suggest ideas from this persona
```

Flow:

1. Pack persona snapshot plus selected source excerpts.
2. Ask model for candidate ideas.
3. Show candidate list with rationale and evidence.
4. Admin accepts, edits, merges, or rejects.
5. Accepted ideas become draft or private Ideas.

### 3. Idea suggestion from content item

On a content item detail page:

Button:

```text
Extract possible ideas
```

Useful for papers, lab pages, funding calls, or public news items.

### 4. Idea merge flow

Because LLMs will create near-duplicates, merging is required.

Example duplicates:

```text
Home-cage behavior monitoring
Automated home cage phenotyping
Long-duration behavioral monitoring
```

Admin should be able to:

- select duplicate idea
- merge aliases and tags
- preserve evidence refs
- redirect old slug if public
- mark old row `merged`

### 5. Publish flow

Before public visibility:

- title reviewed
- public summary reviewed
- private notes not exposed
- evidence checked
- at least one useful relationship or tag exists
- no obviously sensitive/private language

---

## Public UX

### Public Ideas index

Route:

```text
/ideas
```

Purpose:

A browsable and searchable index of research themes, technical opportunities, and buildable concepts.

Recommended filters:

- idea type
- tags
- related funding availability
- related people/orgs
- Hub capability
- recently updated

Card fields:

```text
Title
Short description
Idea type
Tags
Related counts: people / orgs / funding
Optional effort mix: funding opportunities by effort level
```

### Public Idea detail page

Route:

```text
/ideas/<slug>
```

Recommended sections:

1. Hero summary
2. Why it matters
3. Related people
4. Related organizations
5. Related places
6. Related funding
7. How the Neurotech Hub can help
8. Recent evidence / latest content
9. Submit a related link

### Page tone

Public Idea pages should feel like educational resource pages, not automated surveillance.

Good:

```text
This area connects behavioral neuroscience, embedded sensing, and long-duration experiment monitoring.
```

Avoid:

```text
These labs are high-value sales targets for this capability.
```

### Fun exploratory affordances

Possible future UI components:

- Idea constellation graph
- Related funding radar
- Map of places connected to the idea
- “Buildable with the Hub” badges
- “Recently active” badges
- “Related methods” chips
- “Explore adjacent ideas” section

---

## Admin UX

### Admin Ideas index

Route:

```text
/admin/ideas
```

Columns:

- title
- type
- status
- public?
- related entities count
- funding count
- confidence
- needs review flags
- updated

Filters:

- status
- type
- public/private
- created via
- quality flags
- no related entities
- no public summary
- possible duplicates

Bulk actions:

- mark for review
- archive
- make private
- regenerate summaries
- suggest related funding

### Admin Idea detail page

Sections:

1. Canonical fields
2. Public preview
3. Private notes
4. Related people/orgs/places/funding
5. Evidence refs
6. Suggested matches
7. Quality flags
8. Regenerate/synthesize actions

Suggested action buttons:

```text
Suggest related people
Suggest related organizations
Suggest related funding
Regenerate public summary
Find duplicate ideas
Create collaboration hypothesis
```

The last button belongs to a later phase and can initially be disabled or hidden.

---

## Idea extraction prompt

File:

```text
prompts/idea_extract_from_persona.txt
```

Purpose:

Given a persona snapshot and supporting excerpts, identify practical Ideas that could help organize public discovery and private Hub collaboration reasoning.

### Prompt input

```text
ENTITY_TYPE
ENTITY_NAME
PERSONA_JSON_OR_TEXT
RECENT_CONTENT_EXCERPTS
HUB_CAPABILITY_SUMMARY optional
EXISTING_IDEA_TITLES optional
```

### Desired JSON output

```json
{
  "ideas": [
    {
      "title": "",
      "idea_type": "research_theme|technical_capability|buildable_concept|method_cluster|funding_theme|strategic_area|public_resource_topic|unknown",
      "short_description": "",
      "public_summary_draft": "",
      "private_summary_draft": "",
      "hub_relevance": "",
      "buildable_angle": "",
      "funding_angle": "",
      "tags": [],
      "aliases": [],
      "related_entity_rationale": "",
      "evidence_refs": [],
      "confidence_score": 0.0,
      "quality_flags": []
    }
  ]
}
```

### Prompt guidance

The model should:

- Prefer ideas that are useful for exploration or collaboration.
- Avoid generic scientific fields unless they are meaningfully scoped.
- Suggest 3-8 ideas, not dozens.
- Mark uncertainty clearly.
- Include aliases for duplicate detection.
- Separate public-safe language from private Hub reasoning.
- Avoid implying private intent or unverified need.

---

## Idea public page prompt

File:

```text
prompts/idea_public_page.txt
```

Purpose:

Generate or refresh a public-facing summary for an Idea from accepted evidence and relationships.

### Desired JSON output

```json
{
  "short_description": "",
  "public_summary": "",
  "why_it_matters": "",
  "how_hub_can_help": "",
  "related_methods": [],
  "related_tags": [],
  "suggested_page_title": "",
  "confidence": 0.0,
  "missing_information": []
}
```

### Provider recommendation

- **Ollama** for draft summaries.
- **OpenAI** for public pages that will be featured, externally shared, or used as flagship Hub-facing content.

---

## Idea duplicate detection

Duplicate detection should combine simple heuristics and LLM review.

### Heuristic signals

- normalized title match
- alias overlap
- tag overlap
- high token similarity
- same related entities
- same source content

### LLM duplicate check

File:

```text
prompts/idea_duplicate_check.txt
```

Input:

```text
candidate idea
list of existing similar ideas
```

Output:

```json
{
  "duplicates": [
    {
      "existing_idea_id": 0,
      "relationship": "same|overlaps|broader|narrower|distinct",
      "rationale": "",
      "recommended_action": "merge|keep_separate|make_alias|needs_review"
    }
  ]
}
```

Provider:

- Ollama is usually sufficient.
- OpenAI only when merging a high-visibility public idea or resolving many ambiguous candidates.

---

## Provider and cost policy

### Ollama default tasks

Use local Ollama for:

- extracting candidate ideas from personas
- extracting candidate ideas from content items
- tagging
- alias suggestions
- broad duplicate detection
- draft public summaries
- draft Hub relevance notes

### OpenAI preferred tasks

Use OpenAI for:

- polished public Idea pages
- flagship public content
- high-value collaboration reasoning
- ambiguous duplicate resolution that affects public pages
- final synthesis used in collaboration hypotheses

### Cost controls

- Store model output in `synthesized_json`.
- Store `generated_at` and provider metadata.
- Regenerate only when source persona/content fingerprint changes.
- Limit candidate ideas per run.
- Use existing persona snapshots rather than repacking full content whenever possible.
- Use shorter prompts for duplicate detection.
- Avoid OpenAI for bulk idea extraction unless explicitly requested.

---

## Relationship to Funding

Ideas make funding useful.

Without Ideas:

```text
Funding ↔ Person
Funding ↔ Organization
```

This can become noisy.

With Ideas:

```text
Funding ↔ Idea ↔ Person
Funding ↔ Idea ↔ Organization
Funding ↔ Idea ↔ Place
Funding ↔ Idea ↔ Hub capability
```

This makes the explanation cleaner:

```text
This funding opportunity may support early-stage technology development.
This idea is about low-power home-cage monitoring.
These people/orgs appear connected to that idea.
The Hub has relevant embedded hardware and behavioral system capabilities.
```

Funding cards can show related Ideas publicly. Admin views can use Ideas to generate collaboration hypotheses.

---

## Relationship to Collaboration Hypotheses

A future Collaboration Hypothesis should often be centered on an Idea.

Example:

```text
Target: Lab X
Idea: Automated home-cage behavioral monitoring
Funding: Foundation Y pilot award
Hub capability: Low-power embedded sensing + behavioral device prototyping
Hypothesis: The Hub could help Lab X prototype a long-duration monitoring module that fits the funding call.
```

The Idea provides the semantic bridge that makes the hypothesis understandable.

---

## Relationship to existing personas

Person, organization, and building personas already synthesize focus areas, methods, keywords, projects, and notes from owned-source evidence.

The Idea layer should reuse that work:

1. Build or refresh persona.
2. Extract candidate Ideas from persona.
3. Suggest links between persona entity and Ideas.
4. Admin accepts or rejects.
5. Public pages display reviewed links only.

Avoid re-ingesting all raw content when a persona snapshot already contains enough signal.

---

## Suggested implementation phases

### Phase 3A — Manual Ideas MVP

Deliverables:

- `Idea` model and migration.
- Admin Ideas CRUD.
- Public Ideas index.
- Public Idea detail page.
- Manual links to people/orgs/places/funding.
- Basic tags and aliases.

Acceptance criteria:

- Admin can create, edit, archive, and publish an Idea.
- Public users can view public Ideas.
- Private fields are not exposed publicly.
- Idea pages can show manually related funding and entities.

### Phase 3B — Idea extraction from personas

Deliverables:

- Persona-to-Idea extraction prompt.
- Admin action to suggest Ideas from a persona.
- Review screen for candidate Ideas.
- Accept/reject/merge flow.

Acceptance criteria:

- Model returns valid JSON candidate ideas.
- Candidates include confidence, rationale, aliases, and evidence references.
- Admin can accept a candidate without manually copying fields.
- Accepted candidate creates or links to an Idea.

### Phase 3C — Duplicate detection and merge

Deliverables:

- Similar idea search.
- Duplicate check prompt.
- Merge UI.
- Alias preservation.

Acceptance criteria:

- Near-duplicate idea titles are detected.
- Admin can merge two Ideas.
- Public slugs remain stable or redirect cleanly.
- Evidence and relationships are preserved.

### Phase 3D — Public Idea page polish

Deliverables:

- Public page synthesis prompt.
- Public-safe summary review.
- Related entity cards.
- Funding cards on Idea pages.
- Hub capability section.

Acceptance criteria:

- Public Idea pages are useful without exposing private lead logic.
- Admin can preview public pages before publishing.
- Page content can be regenerated from reviewed evidence.

### Phase 3E — Matching preparation

Deliverables:

- `IdeaEntityLink` or initial bridge to future `MatchEdge`.
- Suggested links between Ideas and people/orgs/funding.
- Admin accept/reject controls.

Acceptance criteria:

- Idea pages can show reviewed relationships.
- Suggested relationships are stored separately from accepted ones.
- Future matching engine can reuse or migrate the relationship records.

---

## Tests

### Model tests

- Create Idea with required fields.
- Slug generation works and avoids collisions.
- Public/private fields remain distinct.
- Status transitions work.
- JSON fields store expected structures.

### Admin workflow tests

- Admin can create, edit, publish, archive.
- Admin can add/remove related entities.
- Admin can accept model-suggested Idea.
- Admin can merge duplicate Ideas.

### Public route tests

- Public Ideas index only shows public Ideas.
- Draft/private/archived Ideas are hidden.
- Public detail page does not expose private summary or private notes.
- Related funding/entities only show public-safe relationships.

### Prompt tests

- Idea extraction prompt returns parseable JSON.
- Missing/weak evidence produces low-confidence ideas or no ideas.
- Duplicate check prompt distinguishes same vs. overlapping vs. distinct.
- Public page prompt avoids private lead language.

### Cost/provider tests

- Ollama is default for bulk extraction.
- OpenAI is only used when configured or explicitly requested.
- Regeneration respects fingerprints/caching.
- Failed LLM calls do not publish unreviewed content.

---

## Quality flags

Recommended flags:

```text
too_broad
too_narrow
duplicate_possible
needs_review
weak_evidence
private_language_present
no_public_summary
no_related_entities
no_funding_links
high_public_value
high_hub_relevance
```

These flags can power admin filters and review queues.

---

## Example Idea record

```json
{
  "title": "Automated home-cage behavioral monitoring",
  "idea_type": "buildable_concept",
  "status": "public",
  "is_public": true,
  "short_description": "Systems that monitor animal behavior continuously in the home cage using sensors, embedded devices, and automated data capture.",
  "public_summary": "Automated home-cage behavioral monitoring connects neuroscience, behavioral engineering, embedded sensing, and long-duration data collection. These systems can reduce manual observation burden and make behavior visible across longer experimental windows.",
  "private_summary": "Strong Hub fit because it maps to embedded hardware, low-power sensing, behavioral device design, data logging, and Hublink-style data visibility.",
  "hub_relevance": "The Hub can help design, prototype, and deploy custom monitoring modules for long-running behavioral experiments.",
  "buildable_angle": "Potential builds include sensorized running wheels, event counters, reward-delivery modules, environmental logging nodes, and synchronized gateway/cloud data systems.",
  "funding_angle": "Potentially relevant to pilot awards, shared instrumentation, technology-development grants, and team-science mechanisms.",
  "tags": [
    "home cage",
    "behavior",
    "embedded sensing",
    "long-duration monitoring",
    "data logging"
  ],
  "aliases": [
    "home-cage phenotyping",
    "automated behavioral monitoring",
    "long-term behavioral sensing"
  ],
  "hub_capabilities": [
    "embedded systems",
    "behavioral hardware",
    "low-power sensing",
    "data logging",
    "cloud-connected devices"
  ],
  "confidence_score": 0.86,
  "quality_flags": [
    "high_public_value",
    "high_hub_relevance"
  ]
}
```

---

## Agent work packages

### Agent A — Data model

Owns:

- `Idea` model
- `IdeaEntityLink` model if used
- migrations
- slug handling
- status constants
- tests

### Agent B — Admin UX

Owns:

- Ideas CRUD
- idea review screen
- manual relationship editor
- duplicate merge flow
- publish/private controls

### Agent C — Public UX

Owns:

- Ideas index
- Idea detail page
- related entity cards
- related funding cards
- Hub relevance section

### Agent D — Prompt engineering

Owns:

- persona-to-idea extraction prompt
- content-to-idea extraction prompt
- public page synthesis prompt
- duplicate detection prompt
- JSON parsing and validation examples

### Agent E — Provider/cost integration

Owns:

- Ollama/OpenAI routing
- provider metadata storage
- caching/fingerprints
- retry/fallback behavior
- cost logging hooks if available

---

## Open questions

1. Should Ideas be globally reusable across all Synapse deployments, or should they be Hub-specific by default?
2. Should broad/narrow Idea relationships be modeled now, or deferred until duplicates become painful?
3. Should public users be able to submit a new Idea directly, or only submit URLs that later generate Ideas?
4. Should funding pages be allowed to create new Ideas automatically, or only suggest them for admin review?
5. Should Hub capabilities be a formal model or remain JSON/tags for now?

Recommended defaults:

- Make Ideas Hub-specific for now.
- Defer formal hierarchy.
- Let public users submit URLs, not freeform Ideas initially.
- Funding can suggest Ideas, but admin must review.
- Keep Hub capabilities as JSON/tags until matching needs more structure.

---

## Summary

The Idea layer is what turns Synapse from an entity intelligence system into a research opportunity graph.

People, organizations, places, and funding are all important, but Ideas explain why they belong together.

The near-term goal is simple:

1. Let admins create and publish Ideas.
2. Let Synapse suggest Ideas from personas and content.
3. Let public users explore Ideas as useful resource pages.
4. Let future matching and collaboration hypotheses use Ideas as the central bridge.

