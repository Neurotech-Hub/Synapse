# Matching and Leads Spec

## Purpose

This document defines the first version of Synapse's matching and lead-generation layer.

The goal is to move from static entity summaries toward **evidence-backed collaboration hypotheses** for the Neurotech Hub. Synapse should not merely say that a person, organization, idea, or funding opportunity is "related" to another entity. It should explain why the connection matters, how strong the evidence is, what the Hub could plausibly contribute, and what action should happen next.

This layer connects:

- People
- Organizations
- Buildings / places
- Ideas
- Funding opportunities
- Hub capabilities
- Content evidence
- Persona snapshots
- Public discovery pages
- Private lead workflows

The most important product principle is:

> A lead is not a sales prospect. A lead is an evidence-backed collaboration hypothesis.

---

## Relationship to prior specs

This spec assumes the following documents exist:

- `docs/roadmap_public_site_leads_funding.md`
- `docs/funding_model.md`
- `docs/effort_index.md`
- `docs/idea_model.md`

The prior specs define funding opportunities, funding synthesis, effort classification, and ideas. This document defines how Synapse should connect those pieces into useful matches and actionable Hub-facing opportunities.

---

## Existing Synapse baseline

Synapse already has several pieces that support this layer:

- `ContentItem` evidence from RSS feeds and HTML snapshots.
- Public URL submission and admin source approval.
- `PersonaSnapshot` records for people, organizations, and buildings / places.
- Organization and place rollups.
- A Hub-centric lead report pipeline.
- Public and admin surfaces.
- Prompt routing through local Ollama and OpenAI providers.
- Evidence caps and prompt budget controls.

This spec should extend those capabilities rather than replace them.

---

## Scope

This spec covers:

- Match concepts and terminology.
- `MatchEdge` data model.
- `MatchRun` / batch tracking model.
- Collaboration hypothesis model.
- Candidate generation.
- Match scoring.
- Evidence requirements.
- LLM provider strategy.
- Admin UX.
- Public UX exposure.
- Prompt templates.
- Acceptance criteria.
- Agent work packages.

This spec does **not** cover:

- Full public site visual design.
- Graph visualization implementation.
- Funding ingestion details.
- Idea extraction details.
- Email sending / outreach automation.
- CRM integration.
- Multi-user tenancy.

---

## Core concepts

### Match

A **Match** is a scored relationship between two entities.

Examples:

- A person matches an idea.
- An organization matches a funding opportunity.
- A funding opportunity matches a Hub capability.
- A building matches an idea because many affiliated people work in that area.

A match is directional but can be displayed bidirectionally.

Example:

```text
FundingOpportunity -> Idea
NIH BRAIN mechanism -> closed-loop behavioral systems
```

The direction matters because the rationale differs. A funding-to-idea match asks, "What could this opportunity support?" An idea-to-funding match asks, "What money could help advance this idea?"

### Lead

A **Lead** is an operational object for the Hub.

It should usually involve:

- A target person, organization, or place.
- A relevant idea.
- A Hub capability fit.
- Optional funding alignment.
- Evidence from the target's corpus.
- A recommended action.

### Collaboration Hypothesis

A **CollaborationHypothesis** is the preferred future form of a lead.

It should state:

```text
Because Target appears to work on X using Y, and because the Hub can support Z, there may be a meaningful collaboration around Idea A. Funding Opportunity B may support this direction, but its effort level is moderate/heavy/mild/unknown.
```

This language keeps the system careful. It avoids pretending that inferred needs are facts.

### Candidate

A **Candidate** is a possible match before expensive scoring.

Examples:

- Person and idea share tags.
- Organization and funding share keywords.
- Funding deadline is active and amount is relevant.
- Person's persona contains methods aligned with a Hub capability.

Candidate generation should be cheap and broad. LLM scoring should only operate on filtered candidates.

---

## Design principles

1. **Evidence first.**
   Every important match should have supporting evidence: persona fields, content item excerpts, source URLs, manually curated notes, or funding synthesis.

2. **Do not collapse effort into value.**
   A heavy grant can still be strategically important. Effort index should be displayed and used for prioritization, but should not automatically suppress high-value opportunities.

3. **Use cheap filters before expensive synthesis.**
   Use tags, keywords, dates, status, and simple scoring before LLM calls.

4. **Make scores explainable.**
   A single number is not enough. Store component scores and rationale.

5. **Keep public and private surfaces separate.**
   Public pages can show related entities. Private admin pages can show lead scores, inferred needs, recommended actions, and outreach strategy.

6. **Support manual curation.**
   Admins should be able to accept, reject, hide, pin, and override matches.

7. **Prefer incremental enrichment.**
   A match can start as a weak tag-overlap edge and later be upgraded into a reviewed collaboration hypothesis.

8. **Do not over-personalize public pages.**
   Public discovery should feel generous and exploratory, not surveillance-like.

---

## Public/private boundary

### Public-safe

Public pages may show:

- Related ideas.
- Related funding opportunities.
- Related people or organizations.
- Public summaries.
- Topic tags.
- Method tags.
- External source links.
- General Hub capability connections.

Example public text:

```text
This funding opportunity may be relevant to automated behavioral systems, chronic recording tools, and computational ethology.
```

### Private-only

Admin-only views may show:

- Lead score.
- Relationship path.
- Inferred technical bottleneck.
- Outreach angle.
- Strategic priority.
- Funding effort/value tradeoff.
- Internal Hub rationale.
- Contact status.
- Dismissal reason.

Example private text:

```text
This lab may be a strong pilot target because recent publications suggest a need for custom home-cage instrumentation and the funding deadline creates a near-term reason to engage.
```

---

## Proposed package structure

```text
app/matching/
  __init__.py
  models.py
  candidates.py
  scoring.py
  evidence.py
  prompts.py
  provider.py
  services.py
  public.py
  admin.py

app/leads/
  hypotheses.py
  scoring.py
  actions.py
```

If preserving the current `app/leads/` package is simpler, `app/matching/` can initially contain only candidate and edge logic while collaboration hypothesis generation stays in `app/leads/`.

---

## Data model: MatchEdge

`MatchEdge` is the base relationship object.

```python
class MatchEdge(db.Model):
    __tablename__ = "match_edges"

    id = db.Column(db.Integer, primary_key=True)

    source_type = db.Column(db.String(64), nullable=False)
    source_id = db.Column(db.Integer, nullable=False)
    target_type = db.Column(db.String(64), nullable=False)
    target_id = db.Column(db.Integer, nullable=False)

    match_type = db.Column(db.String(80), nullable=False)

    score_total = db.Column(db.Float, nullable=True)
    score_topic_fit = db.Column(db.Float, nullable=True)
    score_method_fit = db.Column(db.Float, nullable=True)
    score_hub_fit = db.Column(db.Float, nullable=True)
    score_funding_fit = db.Column(db.Float, nullable=True)
    score_evidence_strength = db.Column(db.Float, nullable=True)
    score_recency = db.Column(db.Float, nullable=True)
    score_strategic_value = db.Column(db.Float, nullable=True)
    score_effort_reasonableness = db.Column(db.Float, nullable=True)

    rationale = db.Column(db.Text, nullable=True)
    public_rationale = db.Column(db.Text, nullable=True)
    private_rationale = db.Column(db.Text, nullable=True)

    evidence_json = db.Column(db.JSON, nullable=True)
    features_json = db.Column(db.JSON, nullable=True)
    synthesized_json = db.Column(db.JSON, nullable=True)

    provider = db.Column(db.String(32), nullable=True)
    model_name = db.Column(db.String(120), nullable=True)
    prompt_version = db.Column(db.String(80), nullable=True)
    pipeline_version = db.Column(db.String(80), nullable=True)

    status = db.Column(db.String(32), default="candidate", nullable=False)
    visibility = db.Column(db.String(32), default="private", nullable=False)

    reviewed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
```

### Entity type values

Recommended values:

```text
person
organization
building
region
idea
funding_opportunity
hub_capability
content_item
```

### Match status values

```text
candidate
scored
reviewed
accepted
rejected
hidden
stale
```

### Visibility values

```text
private
public_candidate
public
hidden
```

Default should be `private`.

---

## Data model: MatchRun

A `MatchRun` tracks batch generation.

```python
class MatchRun(db.Model):
    __tablename__ = "match_runs"

    id = db.Column(db.Integer, primary_key=True)
    run_type = db.Column(db.String(80), nullable=False)
    source_type = db.Column(db.String(64), nullable=True)
    source_id = db.Column(db.Integer, nullable=True)

    status = db.Column(db.String(32), default="queued", nullable=False)
    provider = db.Column(db.String(32), nullable=True)
    model_name = db.Column(db.String(120), nullable=True)
    prompt_version = db.Column(db.String(80), nullable=True)
    pipeline_version = db.Column(db.String(80), nullable=True)

    candidates_count = db.Column(db.Integer, default=0, nullable=False)
    scored_count = db.Column(db.Integer, default=0, nullable=False)
    accepted_count = db.Column(db.Integer, default=0, nullable=False)
    error_count = db.Column(db.Integer, default=0, nullable=False)

    input_fingerprint = db.Column(db.String(128), nullable=True)
    params_json = db.Column(db.JSON, nullable=True)
    result_summary_json = db.Column(db.JSON, nullable=True)
    error_text = db.Column(db.Text, nullable=True)

    started_at = db.Column(db.DateTime, nullable=True)
    finished_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
```

This makes matching auditable and helps prevent accidental repeated expensive runs.

---

## Data model: CollaborationHypothesis

This is the private operational lead object.

```python
class CollaborationHypothesis(db.Model):
    __tablename__ = "collaboration_hypotheses"

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(240), nullable=False)
    target_type = db.Column(db.String(64), nullable=False)
    target_id = db.Column(db.Integer, nullable=False)

    idea_id = db.Column(db.Integer, db.ForeignKey("ideas.id"), nullable=True)
    funding_opportunity_id = db.Column(db.Integer, db.ForeignKey("funding_opportunities.id"), nullable=True)

    summary = db.Column(db.Text, nullable=True)
    evidence_summary = db.Column(db.Text, nullable=True)
    hub_fit_summary = db.Column(db.Text, nullable=True)
    funding_fit_summary = db.Column(db.Text, nullable=True)
    effort_summary = db.Column(db.Text, nullable=True)
    recommended_action = db.Column(db.Text, nullable=True)
    outreach_angle = db.Column(db.Text, nullable=True)

    score_total = db.Column(db.Float, nullable=True)
    score_fit = db.Column(db.Float, nullable=True)
    score_timing = db.Column(db.Float, nullable=True)
    score_funding = db.Column(db.Float, nullable=True)
    score_effort_alignment = db.Column(db.Float, nullable=True)
    score_relationship_path = db.Column(db.Float, nullable=True)
    score_strategic_value = db.Column(db.Float, nullable=True)
    score_evidence_strength = db.Column(db.Float, nullable=True)

    evidence_json = db.Column(db.JSON, nullable=True)
    source_match_edge_ids_json = db.Column(db.JSON, nullable=True)
    synthesized_json = db.Column(db.JSON, nullable=True)

    status = db.Column(db.String(32), default="draft", nullable=False)
    priority = db.Column(db.String(32), default="normal", nullable=False)

    provider = db.Column(db.String(32), nullable=True)
    model_name = db.Column(db.String(120), nullable=True)
    prompt_version = db.Column(db.String(80), nullable=True)
    pipeline_version = db.Column(db.String(80), nullable=True)

    reviewed_at = db.Column(db.DateTime, nullable=True)
    contacted_at = db.Column(db.DateTime, nullable=True)
    dismissed_at = db.Column(db.DateTime, nullable=True)
    dismissal_reason = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
```

### Hypothesis status values

```text
draft
reviewed
active
contacted
waiting
won
lost
dismissed
stale
```

### Priority values

```text
low
normal
high
urgent
strategic
```

---

## Match types

Recommended `match_type` values:

```text
person_to_idea
organization_to_idea
building_to_idea
funding_to_idea
funding_to_person
funding_to_organization
funding_to_building
hub_to_person
hub_to_organization
hub_to_idea
hub_to_funding
idea_to_funding
idea_to_person
idea_to_organization
organization_to_funding
person_to_funding
```

Do not worry if these feel redundant. Directional match types make prompts and UI labels simpler.

---

## Candidate generation

Candidate generation should be cheap and mostly deterministic.

### Funding to idea candidates

Use:

- Funding `topic_tags_json`.
- Funding `method_tags_json`.
- Idea tags and aliases.
- Public summary keyword overlap.
- Sponsor/mechanism keywords.
- Active/upcoming status.

Candidate threshold:

```text
At least one strong tag overlap
OR two weak keyword overlaps
OR manual pin
```

### Funding to person candidates

Use:

- Person persona focus areas.
- Person persona methods.
- Recent content item titles/snippets.
- Funding topic/method tags.
- Organization affiliation if available.
- Idea matches as bridge edges.

Prefer indirect matching:

```text
funding -> idea -> person
```

over raw keyword matching when possible.

### Funding to organization candidates

Use:

- Organization persona / rollup.
- Affiliated people.
- Building/place rollups.
- Existing idea edges.
- Funding eligibility summary.

### Hub to target candidates

Use:

- Hub persona / bundled corpus.
- Hub capability tags.
- Target persona methods and projects.
- Known technical bottleneck terms.
- Recent content evidence.

### Idea to target candidates

Use:

- Idea tags.
- Persona focus/method fields.
- Existing funding or content matches.
- Manual admin associations.

---

## Cheap feature extraction

Before LLM scoring, compute features like:

```json
{
  "shared_topic_tags": ["home-cage behavior", "closed-loop systems"],
  "shared_method_tags": ["electrophysiology", "behavioral tracking"],
  "deadline_days": 74,
  "funding_status": "active",
  "funding_effort_index": "moderate",
  "target_recent_items_count": 5,
  "persona_age_days": 12,
  "manual_boost": false,
  "known_affiliation_bridge": true,
  "evidence_item_count": 4
}
```

These features should be stored in `features_json` on `MatchEdge`.

---

## Scoring framework

### Score range

All component scores should use:

```text
0.0 to 1.0
```

Use `null` when a score is not applicable.

### General match score

```text
score_total =
  0.25 * topic_fit
+ 0.20 * method_fit
+ 0.20 * evidence_strength
+ 0.15 * recency
+ 0.10 * strategic_value
+ 0.10 * hub_fit_or_funding_fit
```

The formula can vary by match type, but weights should be stored in `synthesized_json` or `features_json` for auditability.

### Funding match score

```text
funding_match_score =
  0.25 * topic_fit
+ 0.20 * method_fit
+ 0.15 * eligibility_fit
+ 0.15 * funding_relevance
+ 0.10 * deadline_urgency
+ 0.10 * evidence_strength
+ 0.05 * effort_reasonableness
```

### Collaboration hypothesis score

```text
hypothesis_score =
  0.25 * fit
+ 0.15 * timing
+ 0.20 * funding
+ 0.10 * effort_alignment
+ 0.10 * relationship_path
+ 0.10 * strategic_value
+ 0.10 * evidence_strength
```

### Important effort rule

Effort index should not be treated as a simple penalty.

Recommended interpretation:

```text
mild:
  easier to act on, good for pilot leads, lower institutional burden

moderate:
  good default action range, often best for near-term collaborations

heavy:
  high burden, but may be strategically important if value and fit are high

unknown:
  do not over-score; flag for review
```

A heavy opportunity can produce a high-priority strategic lead. A mild opportunity can produce a high-priority quick-win lead.

---

## Evidence requirements

A reviewed match should include at least one evidence object.

Recommended evidence object shape:

```json
{
  "kind": "persona_field|content_item|funding_summary|manual_note|match_edge",
  "entity_type": "person",
  "entity_id": 123,
  "content_item_id": 456,
  "title": "",
  "url": "",
  "excerpt": "",
  "field": "methods",
  "confidence": 0.8
}
```

For public display, evidence should be limited to public-safe material.

For private display, evidence can include internal notes, private rationale, and accepted/rejected match history.

---

## Matching workflow v1

### Workflow: Generate matches for one funding opportunity

```text
Admin opens Funding detail page
Admin clicks Generate matches
System collects active ideas, people, organizations, and buildings
System generates cheap candidates
System scores candidates with heuristics
System sends top candidates to Ollama for rough rationale
System stores MatchEdges
Admin reviews top matches
Admin accepts/rejects/hides matches
Accepted matches can be used for CollaborationHypotheses
```

### Workflow: Generate matches for one idea

```text
Admin opens Idea detail page
Admin clicks Generate matches
System finds related people, organizations, places, funding, and Hub capabilities
System stores MatchEdges
Public-safe accepted matches can appear on Idea public page
Private matches remain admin-only
```

### Workflow: Generate collaboration hypothesis

```text
Admin selects target person/org/place
Optional: select idea
Optional: select funding opportunity
System gathers accepted MatchEdges and evidence
System drafts CollaborationHypothesis
Admin reviews, edits, prioritizes, or dismisses
```

---

## Provider strategy

### Ollama default tasks

Use Ollama for:

- Broad match rationale drafts.
- Tag-overlap interpretation.
- Low-stakes internal scoring.
- Public-safe related-entity blurbs.
- Batch candidate summaries.
- Re-running many candidates at low cost.

### OpenAI preferred tasks

Use OpenAI for:

- Final collaboration hypothesis synthesis.
- High-value target reports.
- Complex multi-entity reasoning.
- Public copy where quality matters.
- JSON repair fallback after local model failure.
- Strategic lead summaries for human review.

### No-LLM tasks

Use deterministic code for:

- Tag overlap.
- Deadline calculations.
- Active/expired funding status.
- Basic effort score mapping.
- Recency scoring.
- Manual boosts.
- Search filtering.

### Environment variables

Recommended additions:

```text
SYNAPSE_LLM_MATCH_PROVIDER=ollama|openai|auto
SYNAPSE_LLM_MATCH_FALLBACK_OPENAI=0|1
SYNAPSE_LLM_HYPOTHESIS_PROVIDER=ollama|openai|auto
SYNAPSE_OPENAI_MATCH_MODEL=
SYNAPSE_OPENAI_HYPOTHESIS_MODEL=
SYNAPSE_MATCH_PIPELINE_SEMVER=1
SYNAPSE_MATCH_CANDIDATE_LIMIT=100
SYNAPSE_MATCH_LLM_LIMIT=20
SYNAPSE_MATCH_MIN_SCORE=0.35
```

Default behavior:

```text
Match scoring: Ollama or deterministic
Collaboration hypothesis: OpenAI if available, otherwise Ollama
```

---

## Prompt templates

Recommended prompt files:

```text
prompts/match_funding_to_idea.txt
prompts/match_funding_to_entity.txt
prompts/match_idea_to_entity.txt
prompts/match_hub_to_target.txt
prompts/collaboration_hypothesis.txt
prompts/outreach_angle.txt
prompts/lead_score_explain.txt
```

---

## Prompt: match_funding_to_entity

Expected output:

```json
{
  "match": true,
  "score_total": 0.0,
  "score_topic_fit": 0.0,
  "score_method_fit": 0.0,
  "score_eligibility_fit": 0.0,
  "score_funding_relevance": 0.0,
  "score_deadline_urgency": 0.0,
  "score_evidence_strength": 0.0,
  "score_effort_reasonableness": 0.0,
  "public_rationale": "",
  "private_rationale": "",
  "supporting_evidence": [],
  "risks_or_uncertainties": [],
  "recommended_next_step": "",
  "confidence": 0.0
}
```

Prompt guidance:

```text
You are evaluating whether a funding opportunity plausibly matches a research entity.
Do not invent facts.
Use only the provided funding summary, persona fields, and evidence excerpts.
Distinguish between direct evidence and weak inference.
Do not treat heavy effort as bad by itself.
Return JSON only.
```

---

## Prompt: match_idea_to_entity

Expected output:

```json
{
  "match": true,
  "score_total": 0.0,
  "score_topic_fit": 0.0,
  "score_method_fit": 0.0,
  "score_evidence_strength": 0.0,
  "score_recency": 0.0,
  "score_strategic_value": 0.0,
  "public_rationale": "",
  "private_rationale": "",
  "evidence_refs": [],
  "confidence": 0.0
}
```

Prompt guidance:

```text
Assess whether the entity's documented work is meaningfully related to this idea.
Prefer concrete methods, project titles, publications, and repeated themes.
Avoid over-matching based on one generic word.
Return JSON only.
```

---

## Prompt: collaboration_hypothesis

Expected output:

```json
{
  "title": "",
  "summary": "",
  "evidence_summary": "",
  "hub_fit_summary": "",
  "funding_fit_summary": "",
  "effort_summary": "",
  "recommended_action": "",
  "outreach_angle": "",
  "score_fit": 0.0,
  "score_timing": 0.0,
  "score_funding": 0.0,
  "score_effort_alignment": 0.0,
  "score_relationship_path": 0.0,
  "score_strategic_value": 0.0,
  "score_evidence_strength": 0.0,
  "score_total": 0.0,
  "risks_or_uncertainties": [],
  "missing_information": [],
  "confidence": 0.0
}
```

Prompt guidance:

```text
Create an evidence-backed collaboration hypothesis for the Neurotech Hub.
Do not write as if outreach has already happened.
Do not claim that the target needs something unless the evidence directly supports it.
Use cautious language for inferred opportunities.
If funding is included, discuss effort separately from strategic value.
Recommend a concrete next action.
Return JSON only.
```

---

## Admin UX

### Admin: Matching dashboard

Path suggestion:

```text
/admin/matches
```

Sections:

- Recent match runs.
- High-scoring unreviewed matches.
- Accepted matches.
- Rejected/hidden matches.
- Stale matches.
- Provider/cost summary.

Filters:

- Source type.
- Target type.
- Match type.
- Score range.
- Status.
- Visibility.
- Provider.
- Has funding.
- Has idea.
- Effort index.

### Admin: Entity detail panels

People/org/place/idea/funding pages should show:

```text
Related ideas
Related funding
Related people/orgs/places
Hub fit
Collaboration hypotheses
Match history
```

Each match card should show:

- Score.
- Match type.
- Public rationale.
- Private rationale.
- Evidence count.
- Provider/model.
- Status.
- Actions.

Actions:

```text
Accept
Reject
Hide
Pin
Regenerate
Create hypothesis
Make public
Keep private
```

### Admin: Collaboration hypothesis page

Path suggestion:

```text
/admin/hypotheses
```

Card groups:

```text
Best now
Funding-aligned
Easy pilot
Strategic heavy lift
Needs relationship-building
Needs review
Dismissed
```

Hypothesis detail should include:

- Target.
- Idea.
- Funding opportunity.
- Score breakdown.
- Evidence summary.
- Hub fit.
- Recommended action.
- Outreach angle.
- Linked matches.
- Status history.

---

## Public UX

Public pages should not expose raw lead logic, but they can benefit from accepted public-safe matches.

### Public idea page

May show:

```text
Related people
Related organizations
Related places
Related funding opportunities
Related latest items
How the Hub can help
```

### Public funding page

May show:

```text
Related ideas
Relevant methods
Possible Hub support areas
External link
Effort index
Deadline / amount text if available
```

### Public person/org/place page

May show:

```text
Related ideas
Selected public funding opportunities
Recent public evidence
```

Avoid:

- Lead score.
- Private rationale.
- Inferred pain points.
- Outreach recommendations.
- Internal prioritization.

---

## Score calibration guidance

Initial score meanings:

```text
0.00-0.24: weak / probably irrelevant
0.25-0.49: possible but low-confidence
0.50-0.69: plausible match
0.70-0.84: strong match
0.85-1.00: exceptional / high-confidence
```

Use conservative defaults. False positives are more costly than missing a few weak matches, especially on public pages.

### Public threshold

Recommended initial threshold:

```text
public display: accepted AND score_total >= 0.60
```

### Private review threshold

Recommended initial threshold:

```text
admin review queue: score_total >= 0.40
```

### Hypothesis generation threshold

Recommended initial threshold:

```text
create hypothesis: at least one accepted match OR admin-selected target
```

Do not block manual hypothesis creation just because scores are incomplete.

---

## Staleness and refresh

A match should become stale when:

- Source persona snapshot changes significantly.
- Funding opportunity expires.
- Funding synthesis changes.
- Idea is archived or merged.
- Pipeline semver changes.
- Admin marks it stale.

Recommended fields:

```text
input_fingerprint
pipeline_version
created_at
updated_at
stale_reason
```

A stale match should remain visible in admin history but not appear publicly unless re-reviewed.

---

## Manual overrides

Admins need explicit control.

Manual fields:

```text
manual_score_override
manual_priority
manual_visibility
manual_rationale
manual_boost
manual_block
```

Rules:

- Manual block prevents regeneration from re-adding the same match.
- Manual boost can push a candidate into LLM scoring.
- Manual visibility controls public display.
- Manual rationale should be stored separately from model rationale.

---

## Relationship to existing LeadReport

Do not remove `LeadReport` immediately.

Recommended migration path:

### Step 1

Keep `LeadReport` as a generated narrative report.

### Step 2

Add `MatchEdge` and use it as structured input to reports.

### Step 3

Add `CollaborationHypothesis` as the new operational object.

### Step 4

Allow `LeadReport` to summarize one or more hypotheses.

### Step 5

Eventually, treat `LeadReport` as an export/view rather than the core lead object.

This avoids breaking existing flows while moving toward structured, reusable intelligence.

---

## API/service functions

Suggested service functions:

```python
def generate_candidates_for_funding(funding_id: int) -> list[Candidate]: ...
def generate_candidates_for_idea(idea_id: int) -> list[Candidate]: ...
def score_candidate(candidate: Candidate, provider: str = "auto") -> MatchEdge: ...
def run_match_batch(run_type: str, source_type: str, source_id: int) -> MatchRun: ...
def create_hypothesis_from_matches(match_edge_ids: list[int]) -> CollaborationHypothesis: ...
def refresh_stale_matches(limit: int = 50) -> MatchRun: ...
```

Candidate object can be a dataclass:

```python
@dataclass
class Candidate:
    source_type: str
    source_id: int
    target_type: str
    target_id: int
    match_type: str
    features: dict
    evidence: list[dict]
    cheap_score: float
```

---

## Testing plan

### Unit tests

- Candidate generation from tag overlap.
- Funding status filtering.
- Deadline urgency scoring.
- Effort alignment scoring.
- Match score composition.
- Public/private visibility filtering.
- Staleness detection.
- Manual block behavior.

### Prompt tests

- Valid JSON parsing.
- Missing evidence produces low confidence.
- Heavy effort is not automatically rejected.
- Generic keyword overlap is not over-scored.
- Public rationale does not include private outreach logic.

### Integration tests

- Generate matches for a funding opportunity.
- Generate matches for an idea.
- Accept a match and expose it publicly.
- Create a collaboration hypothesis from accepted matches.
- Stale match after funding expiration.
- OpenAI fallback behavior when Ollama output fails validation.

---

## Acceptance criteria: MatchEdge MVP

- Admin can generate matches for one funding opportunity.
- System creates deterministic candidates before LLM use.
- System stores `MatchEdge` rows with component scores.
- Admin can accept/reject/hide matches.
- Public pages do not show private matches.
- Match generation can run without OpenAI.
- OpenAI can be enabled for higher-quality synthesis.
- Tests cover candidate generation and score composition.

---

## Acceptance criteria: CollaborationHypothesis MVP

- Admin can create a hypothesis from a person/org/place plus optional idea/funding.
- Hypothesis includes score breakdown.
- Hypothesis includes evidence summary.
- Hypothesis includes recommended next action.
- Hypothesis distinguishes funding value from effort burden.
- Hypothesis can be reviewed, activated, dismissed, or marked stale.
- Existing `LeadReport` flow remains functional.

---

## Agent work packages

### Agent A: Models and migrations

Owns:

- `MatchEdge`
- `MatchRun`
- `CollaborationHypothesis`
- indexes
- migration scripts
- model tests

### Agent B: Candidate generation

Owns:

- tag overlap logic
- funding-to-idea candidates
- idea-to-entity candidates
- hub-to-target candidates
- cheap score features
- candidate tests

### Agent C: Scoring and staleness

Owns:

- component score formulas
- effort alignment logic
- deadline urgency
- evidence strength
- stale detection
- manual overrides

### Agent D: Prompt/provider layer

Owns:

- prompt files
- provider routing
- JSON validation
- fallback behavior
- token/cost logging hooks
- prompt tests

### Agent E: Admin UX

Owns:

- `/admin/matches`
- match cards
- match review actions
- entity detail panels
- hypothesis detail page
- status transitions

### Agent F: Public UX integration

Owns:

- public-safe related entity blocks
- public funding/idea match display
- visibility filters
- public copy constraints

### Agent G: LeadReport migration

Owns:

- preserving existing reports
- feeding MatchEdges into reports
- connecting reports to hypotheses
- compatibility tests

---

## Implementation sequence

Recommended order:

```text
1. Add MatchEdge and MatchRun models.
2. Add deterministic candidate generation for funding -> idea.
3. Add admin match generation/review page.
4. Add funding -> person/org matching through idea bridges.
5. Add CollaborationHypothesis model.
6. Add hypothesis generation from accepted matches.
7. Add public-safe related blocks.
8. Integrate with existing LeadReport as structured inputs.
9. Add staleness, refresh, and manual override flows.
```

Start narrow. Funding-to-idea matching is the best first slice because it is lower-risk, public-friendly, and directly useful for the new Funding and Idea layers.

---

## Open questions

1. Should Hub capabilities be a formal table or stored as JSON in the Hub organization persona for now?
2. Should public users be able to suggest matches?
3. Should match edges be many-to-many visible in a graph view, or only shown as cards at first?
4. Should dismissed hypotheses suppress future matches for a target, or only suppress the exact idea/funding combination?
5. Should `LeadReport` eventually become a PDF/exportable artifact?
6. How much manual relationship tracking should Synapse support before becoming too CRM-like?
7. Should the public site expose funding opportunities before they are reviewed by admin?

---

## Recommended first build slice

Build this first:

```text
FundingOpportunity -> Idea -> Public funding card related ideas
```

Then build:

```text
Idea -> Person/Organization -> Admin review queue
```

Then build:

```text
Accepted matches -> CollaborationHypothesis
```

This sequence creates immediate public-site value while laying the groundwork for private lead generation.

