# Prompt Specs for Synapse Funding, Ideas, Matching, and Public Discovery

## Purpose

This document defines the prompt architecture for the next phase of Synapse: funding opportunities, effort indexing, ideas, matching, collaboration hypotheses, and public-site synthesis.

The goal is to make prompt behavior:

- predictable
- testable
- cost-aware
- provider-aware
- easy for agents to implement incrementally
- safe for public/private boundaries

Synapse already routes LLM work through provider-specific paths for identity/persona generation, HTML enrichment, lead reports, and public feed curation. This document extends that pattern rather than replacing it.

---

## Design principles

### 1. Prompts should produce structured outputs first

Use JSON for extraction, classification, matching, and scoring.

Use prose only after structured data exists.

Bad pattern:

```text
Ask the model to write a whole report and then parse meaning from the report.
```

Preferred pattern:

```text
Extract structured fields → validate → repair if needed → generate short prose from validated fields.
```

---

### 2. Separate extraction from judgment

Extraction prompts should answer:

```text
What does the source say?
```

Judgment prompts should answer:

```text
What does this imply for the Neurotech Hub?
```

Do not combine these too early.

For example, a funding page extraction prompt should not decide whether the Hub should pursue the opportunity. It should identify amount, deadline, eligibility, topics, and effort signals. Matching and collaboration prompts can use that extracted data later.

---

### 3. Keep public and private synthesis separate

Public-facing prompts should produce generous, neutral, exploratory language.

Private prompts may include:
- Hub fit
- likely technical bottlenecks
- collaboration rationale
- lead priority
- outreach angle
- funding strategy

Never expose private scoring or inferred pain points on public pages.

---

### 4. Use cheap/local models for broad work

Default to local Ollama for:
- first-pass extraction
- classification
- tag generation
- rough summaries
- low-stakes matching
- draft public copy

Use OpenAI for:
- malformed or complex pages
- high-value opportunities
- final collaboration hypotheses
- polished public pages
- synthesis across many entities
- JSON repair after repeated local failures
- evaluation/gold-set comparison

---

### 5. Every prompt should declare uncertainty

The app should prefer:

```json
{
  "confidence": 0.62,
  "missing_information": ["deadline not found", "award amount unclear"]
}
```

over hallucinating missing details.

---

## Prompt registry

Recommended location:

```text
prompts/
  funding_extract.txt
  funding_effort_classify.txt
  funding_public_card.txt

  idea_extract_from_persona.txt
  idea_synthesize_page.txt
  idea_match_entity.txt

  match_funding_to_entity.txt
  match_entity_to_idea.txt
  match_hub_to_target.txt

  collaboration_hypothesis.txt
  outreach_angle.txt
  lead_score_explain.txt

  public_entity_summary.txt
  public_place_summary.txt
  public_research_atlas_blurb.txt

  json_repair.txt
```

Optional metadata registry:

```text
app/llm/prompt_registry.py
```

Example:

```python
PROMPTS = {
    "funding_extract": {
        "path": "prompts/funding_extract.txt",
        "default_provider": "ollama",
        "fallback_provider": "openai",
        "output": "json",
        "version": "1.0.0",
    },
    "collaboration_hypothesis": {
        "path": "prompts/collaboration_hypothesis.txt",
        "default_provider": "openai",
        "fallback_provider": "ollama",
        "output": "json",
        "version": "1.0.0",
    },
}
```

---

## Provider policy

### Default provider matrix

| Task | Default | Fallback | Notes |
|---|---:|---:|---|
| Funding extraction | Ollama | OpenAI | Use raw page text; strict JSON |
| Effort classification | Ollama | OpenAI | Can run after heuristic pre-score |
| Funding public card | Ollama | OpenAI | Short, neutral copy |
| Idea extraction from persona | Ollama | OpenAI | Batch-friendly |
| Idea public page synthesis | OpenAI | Ollama | Higher quality public writing |
| Entity-to-idea matching | Ollama | OpenAI | Broad matching pass |
| Funding-to-entity matching | Ollama | OpenAI | Broad matching pass |
| Hub-to-target match | OpenAI | Ollama | More strategic reasoning |
| Collaboration hypothesis | OpenAI | Ollama | Final synthesis; high value |
| Outreach angle | OpenAI | Ollama | Private only |
| JSON repair | Ollama first | OpenAI second | Use deterministic repair prompt |

---

## Token and cost control

### General rules

- Store raw fetched text once.
- Store cleaned text once.
- Store content hash.
- Store synthesis hash.
- Do not re-run prompts if input hash and prompt version are unchanged.
- Summarize long source material before matching.
- Match against compact snapshots, not full corpora, unless explicitly requested.
- Use OpenAI only on top candidate sets when possible.

### Suggested budgets

| Prompt | Input budget | Output budget |
|---|---:|---:|
| funding_extract | 12k-24k chars | 1k-2k tokens |
| funding_effort_classify | 4k-8k chars | 500-800 tokens |
| funding_public_card | 2k-6k chars | 300-600 tokens |
| idea_extract_from_persona | persona snapshot + recent evidence | 1k-2k tokens |
| idea_synthesize_page | compact idea + related entities | 1k-2k tokens |
| match_funding_to_entity | compact funding + compact entity | 800-1500 tokens |
| collaboration_hypothesis | top evidence only | 1.5k-3k tokens |

---

## Shared JSON conventions

All structured prompts should return:

```json
{
  "schema_version": "1.0",
  "confidence": 0.0,
  "missing_information": [],
  "warnings": []
}
```

All scoring fields should be numeric floats from `0.0` to `1.0`.

All categorical labels should use constrained enums.

All rationale fields should be short and evidence-grounded.

---

# Prompt specifications

---

## 1. Funding extraction

### File

```text
prompts/funding_extract.txt
```

### Purpose

Extract lightweight, normalized information from a funding opportunity page.

### Provider

Default: Ollama  
Fallback: OpenAI

### Inputs

```json
{
  "source_url": "",
  "page_title": "",
  "cleaned_text": "",
  "optional_admin_notes": ""
}
```

### Output schema

```json
{
  "schema_version": "1.0",
  "title": "",
  "sponsor_name": "",
  "sponsor_type": "nih|nsf|foundation|nonprofit|internal|industry|government|other|unknown",
  "opportunity_type": "grant|fellowship|prize|contract|seed|equipment|training|other|unknown",
  "one_sentence_summary": "",
  "public_summary": "",
  "eligibility_summary": "",
  "amount_text": "",
  "amount_min": null,
  "amount_max": null,
  "deadline_text": "",
  "deadline_date": null,
  "duration_text": "",
  "topic_tags": [],
  "method_tags": [],
  "eligible_entities": [],
  "collaboration_required": "yes|no|unclear",
  "equipment_allowed": "yes|no|unclear",
  "service_core_allowed": "yes|no|unclear",
  "possible_hub_relevance": [],
  "source_quotes": [],
  "confidence": 0.0,
  "missing_information": [],
  "warnings": []
}
```

### Prompt draft

```text
You are extracting lightweight structured information from a funding opportunity page.

Rules:
- Use only the provided text.
- Do not invent deadlines, amounts, eligibility, or sponsor details.
- If a field is unclear, use null, "unknown", or "unclear".
- Keep summaries short.
- Use broad tags, not overly specific phrases.
- Return valid JSON only.

Source URL:
{{ source_url }}

Page title:
{{ page_title }}

Optional admin notes:
{{ optional_admin_notes }}

Funding page text:
{{ cleaned_text }}

Return JSON matching this schema:
{{ schema }}
```

---

## 2. Funding effort classification

### File

```text
prompts/funding_effort_classify.txt
```

### Purpose

Classify the likely application effort as mild, moderate, heavy, or unknown.

### Important principle

Effort is not the same as value.

A heavy opportunity may still be highly valuable. The effort index should describe expected application burden, not whether the Hub should care.

### Provider

Default: Ollama  
Fallback: OpenAI

### Inputs

```json
{
  "funding_extraction_json": {},
  "heuristic_effort_guess": "",
  "heuristic_rationale": ""
}
```

### Output schema

```json
{
  "schema_version": "1.0",
  "effort_index": "mild|moderate|heavy|unknown",
  "effort_score": 0.0,
  "effort_rationale": "",
  "positive_value_note": "",
  "confidence": 0.0,
  "missing_information": [],
  "warnings": []
}
```

### Prompt draft

```text
Classify the likely application effort for this funding opportunity.

Effort labels:
- mild: small pilot, simple internal application, short proposal, small budget, limited coordination.
- moderate: standard foundation or pilot-style proposal, moderate budget, some narrative and budget work.
- heavy: major NIH/NSF-scale, center-scale, multi-investigator, complex budget, institutional approvals, large award.
- unknown: not enough information.

Rules:
- Do not classify value or strategic importance.
- A heavy opportunity can still be valuable.
- Consider amount, mechanism, duration, required collaboration, institutional requirements, and application complexity.
- Return valid JSON only.

Heuristic guess:
{{ heuristic_effort_guess }}

Heuristic rationale:
{{ heuristic_rationale }}

Funding extraction:
{{ funding_extraction_json }}

Return JSON matching this schema:
{{ schema }}
```

---

## 3. Funding public card

### File

```text
prompts/funding_public_card.txt
```

### Purpose

Generate short public-facing funding copy.

### Provider

Default: Ollama  
Fallback: OpenAI

### Output schema

```json
{
  "schema_version": "1.0",
  "display_title": "",
  "short_summary": "",
  "best_for": [],
  "effort_label": "mild|moderate|heavy|unknown",
  "effort_public_note": "",
  "tags": [],
  "confidence": 0.0,
  "warnings": []
}
```

### Public copy rules

- Neutral and useful.
- Do not imply endorsement.
- Do not expose private Hub strategy.
- Refer users to the source link for details.
- Do not overstate eligibility.

### Prompt draft

```text
Create a short public-facing funding card from the structured funding data.

Rules:
- Keep it concise.
- Do not imply that the Neurotech Hub endorses or administers this opportunity.
- Do not invent details.
- Mention effort in plain language.
- Tell users to check the source link for full details.
- Return valid JSON only.

Funding data:
{{ funding_json }}

Return JSON matching this schema:
{{ schema }}
```

---

## 4. Idea extraction from persona

### File

```text
prompts/idea_extract_from_persona.txt
```

### Purpose

Identify research ideas/themes that can connect people, organizations, places, Hub capabilities, and funding.

### Provider

Default: Ollama  
Fallback: OpenAI

### Inputs

```json
{
  "entity_type": "person|organization|place",
  "entity_name": "",
  "persona_snapshot": {},
  "recent_evidence_summary": ""
}
```

### Output schema

```json
{
  "schema_version": "1.0",
  "candidate_ideas": [
    {
      "title": "",
      "short_description": "",
      "tags": [],
      "methods": [],
      "organisms": [],
      "technologies": [],
      "why_this_entity_matches": "",
      "evidence_strength": 0.0,
      "confidence": 0.0
    }
  ],
  "confidence": 0.0,
  "missing_information": [],
  "warnings": []
}
```

### Prompt draft

```text
Extract candidate research ideas from this entity persona.

An Idea is a reusable research theme or opportunity concept, not just a keyword.
Good examples:
- automated home-cage behavior
- closed-loop neural stimulation
- chronic electrophysiology tooling
- low-power behavioral devices
- computational ethology

Rules:
- Prefer ideas that could connect multiple people, organizations, places, funding opportunities, and Hub capabilities.
- Avoid overly narrow paper titles.
- Avoid generic fields like "neuroscience" unless no better idea is available.
- Use only the provided evidence.
- Return valid JSON only.

Entity type:
{{ entity_type }}

Entity name:
{{ entity_name }}

Persona snapshot:
{{ persona_snapshot }}

Recent evidence:
{{ recent_evidence_summary }}

Return JSON matching this schema:
{{ schema }}
```

---

## 5. Idea public page synthesis

### File

```text
prompts/idea_synthesize_page.txt
```

### Purpose

Generate public-facing copy for an Idea page.

### Provider

Default: OpenAI  
Fallback: Ollama

### Output schema

```json
{
  "schema_version": "1.0",
  "headline": "",
  "short_summary": "",
  "why_it_matters": "",
  "common_methods": [],
  "related_capabilities": [],
  "what_the_hub_can_help_with": [],
  "public_caveats": [],
  "confidence": 0.0,
  "warnings": []
}
```

### Prompt draft

```text
Write public-facing copy for a research idea page.

Rules:
- Be clear, inviting, and exploratory.
- Do not make private lead-generation claims.
- Do not imply that every related person is actively seeking collaboration.
- Keep the copy useful to researchers.
- Avoid hype.
- Return valid JSON only.

Idea:
{{ idea_json }}

Related public entities:
{{ related_entities_json }}

Related funding summaries:
{{ related_funding_json }}

Hub capabilities:
{{ hub_capabilities_json }}

Return JSON matching this schema:
{{ schema }}
```

---

## 6. Funding-to-entity match

### File

```text
prompts/match_funding_to_entity.txt
```

### Purpose

Score whether a funding opportunity plausibly matches a person, organization, or place.

### Provider

Default: Ollama  
Fallback: OpenAI

### Inputs

```json
{
  "funding": {},
  "entity_type": "",
  "entity_snapshot": {},
  "related_ideas": [],
  "hub_context": {}
}
```

### Output schema

```json
{
  "schema_version": "1.0",
  "match_score": 0.0,
  "topic_fit": 0.0,
  "method_fit": 0.0,
  "eligibility_fit": 0.0,
  "hub_capability_fit": 0.0,
  "funding_amount_fit": 0.0,
  "deadline_urgency": 0.0,
  "effort_reasonableness": 0.0,
  "evidence_strength": 0.0,
  "rationale": "",
  "supporting_points": [],
  "concerns": [],
  "recommended_next_step": "ignore|watch|review|strong_review",
  "confidence": 0.0,
  "missing_information": [],
  "warnings": []
}
```

### Prompt draft

```text
Evaluate whether this funding opportunity plausibly matches the entity.

Rules:
- Use only the provided information.
- Do not assume eligibility if unclear.
- Keep rationale evidence-grounded.
- Effort should affect feasibility, not scientific fit.
- Return valid JSON only.

Funding:
{{ funding }}

Entity type:
{{ entity_type }}

Entity snapshot:
{{ entity_snapshot }}

Related ideas:
{{ related_ideas }}

Hub context:
{{ hub_context }}

Return JSON matching this schema:
{{ schema }}
```

---

## 7. Entity-to-idea match

### File

```text
prompts/match_entity_to_idea.txt
```

### Purpose

Score whether an entity is meaningfully related to an Idea.

### Provider

Default: Ollama  
Fallback: OpenAI

### Output schema

```json
{
  "schema_version": "1.0",
  "match_score": 0.0,
  "topic_fit": 0.0,
  "method_fit": 0.0,
  "evidence_strength": 0.0,
  "relationship_type": "direct|adjacent|weak|unknown",
  "rationale": "",
  "supporting_points": [],
  "confidence": 0.0,
  "warnings": []
}
```

### Prompt draft

```text
Evaluate whether the entity is meaningfully related to this research idea.

Rules:
- A direct match means the entity clearly works in this area.
- An adjacent match means the entity uses related methods, organisms, or tools.
- A weak match means there is only a loose connection.
- Do not overfit based on one generic keyword.
- Return valid JSON only.

Entity snapshot:
{{ entity_snapshot }}

Idea:
{{ idea_json }}

Return JSON matching this schema:
{{ schema }}
```

---

## 8. Hub-to-target match

### File

```text
prompts/match_hub_to_target.txt
```

### Purpose

Evaluate whether the Neurotech Hub has a meaningful collaboration fit with a target person, organization, place, idea, or funding opportunity.

### Provider

Default: OpenAI  
Fallback: Ollama

### Output schema

```json
{
  "schema_version": "1.0",
  "hub_fit_score": 0.0,
  "capability_fit": 0.0,
  "technical_need_fit": 0.0,
  "strategic_fit": 0.0,
  "relationship_path_score": 0.0,
  "rationale": "",
  "likely_hub_services": [],
  "possible_pilot_shapes": [],
  "concerns": [],
  "confidence": 0.0,
  "warnings": []
}
```

### Prompt draft

```text
Evaluate whether this target has a meaningful collaboration fit with the Neurotech Hub.

Rules:
- Be evidence-grounded.
- Do not invent a need.
- Distinguish strong evidence from plausible inference.
- Suggest concrete but non-salesy collaboration shapes.
- Return valid JSON only.

Hub persona/corpus:
{{ hub_context }}

Target:
{{ target_json }}

Related ideas:
{{ related_ideas }}

Related funding:
{{ related_funding }}

Return JSON matching this schema:
{{ schema }}
```

---

## 9. Collaboration hypothesis

### File

```text
prompts/collaboration_hypothesis.txt
```

### Purpose

Generate a structured private lead object from validated matches.

### Provider

Default: OpenAI  
Fallback: Ollama

### Output schema

```json
{
  "schema_version": "1.0",
  "title": "",
  "hypothesis_summary": "",
  "why_now": "",
  "evidence_summary": "",
  "hub_fit_summary": "",
  "funding_fit_summary": "",
  "effort_note": "",
  "recommended_action": "",
  "suggested_opening_angle": "",
  "score_fit": 0.0,
  "score_timing": 0.0,
  "score_funding": 0.0,
  "score_effort_feasibility": 0.0,
  "score_relationship_path": 0.0,
  "score_total": 0.0,
  "status_recommendation": "watch|review|active|dismiss",
  "supporting_evidence": [],
  "risks": [],
  "confidence": 0.0,
  "warnings": []
}
```

### Prompt draft

```text
Create a private collaboration hypothesis for the Neurotech Hub.

A collaboration hypothesis is not a sales lead. It is an evidence-grounded guess about a meaningful collaboration the Hub could pursue.

Rules:
- Use only provided evidence and match outputs.
- Distinguish facts from inferences.
- Do not overstate the funding fit if eligibility is unclear.
- Include effort as feasibility, not value.
- Recommend a practical next action.
- Keep the tone strategic and concise.
- Return valid JSON only.

Hub context:
{{ hub_context }}

Target entity:
{{ target_entity }}

Relevant idea:
{{ idea_json }}

Funding opportunity:
{{ funding_json }}

Match outputs:
{{ match_outputs }}

Evidence excerpts:
{{ evidence_excerpts }}

Return JSON matching this schema:
{{ schema }}
```

---

## 10. Outreach angle

### File

```text
prompts/outreach_angle.txt
```

### Purpose

Generate private outreach framing for a reviewed collaboration hypothesis.

### Provider

Default: OpenAI  
Fallback: Ollama

### Output schema

```json
{
  "schema_version": "1.0",
  "angle": "",
  "short_email_subject": "",
  "short_email_body": "",
  "conversation_starter": "",
  "avoid_saying": [],
  "confidence": 0.0,
  "warnings": []
}
```

### Prompt draft

```text
Draft a concise outreach angle for this reviewed collaboration hypothesis.

Rules:
- Be collegial, not salesy.
- Do not mention private scores.
- Do not imply the person needs help unless the evidence directly supports it.
- Focus on shared research opportunity and concrete Hub capabilities.
- Keep email brief.
- Return valid JSON only.

Collaboration hypothesis:
{{ collaboration_hypothesis }}

Hub context:
{{ hub_context }}

Return JSON matching this schema:
{{ schema }}
```

---

## 11. Public entity summary

### File

```text
prompts/public_entity_summary.txt
```

### Purpose

Generate short public summaries for people, organizations, or places.

### Provider

Default: Ollama  
Fallback: OpenAI

### Output schema

```json
{
  "schema_version": "1.0",
  "display_summary": "",
  "research_themes": [],
  "methods": [],
  "public_caveats": [],
  "confidence": 0.0,
  "warnings": []
}
```

### Prompt draft

```text
Create a short public-facing summary for this entity.

Rules:
- Be neutral and evidence-grounded.
- Do not expose private Hub lead reasoning.
- Do not infer needs, pain points, or outreach strategy.
- Avoid overclaiming.
- Return valid JSON only.

Entity snapshot:
{{ entity_snapshot }}

Recent public evidence:
{{ recent_evidence }}

Return JSON matching this schema:
{{ schema }}
```

---

## 12. JSON repair

### File

```text
prompts/json_repair.txt
```

### Purpose

Repair malformed JSON returned by local or remote models.

### Provider

Default: Ollama  
Fallback: OpenAI

### Prompt draft

```text
Repair the following malformed JSON.

Rules:
- Return valid JSON only.
- Preserve the original meaning.
- Do not add new facts.
- If a value is missing or unclear, use null, [], or "".
- Match the requested schema.

Requested schema:
{{ schema }}

Malformed output:
{{ malformed_output }}
```

---

# Prompt evaluation

## Gold examples

Create a small set of hand-reviewed examples:

```text
tests/fixtures/prompts/
  funding_extract/
    nih_r01_like.json
    foundation_seed_grant.json
    unclear_private_foundation.json

  effort_index/
    mild_internal_seed.json
    moderate_foundation_award.json
    heavy_center_grant.json

  matching/
    strong_funding_entity_match.json
    weak_keyword_only_match.json
    ineligible_match.json
```

Each example should include:
- input text
- expected key fields
- acceptable ranges
- disallowed hallucinations

---

## Acceptance criteria

### Funding extraction

- Produces valid JSON.
- Does not invent deadline.
- Does not invent amount.
- Captures source URL.
- Uses `unknown` or `null` when needed.
- Includes confidence and missing information.

### Effort classification

- Classifies large multi-year complex awards as heavy.
- Classifies small internal seed-style awards as mild.
- Uses unknown when amount/mechanism are unclear.
- Does not treat heavy as bad.

### Matching

- Penalizes generic keyword-only matches.
- Distinguishes eligibility uncertainty.
- Returns rationale.
- Returns supporting and concern fields.
- Does not expose private analysis in public outputs.

### Collaboration hypothesis

- Produces concrete next action.
- References funding effort appropriately.
- Distinguishes evidence from inference.
- Does not sound like spam outreach.
- Preserves public/private boundary.

---

# Implementation recommendations

## Add a generic model-call record

Suggested table:

```text
LLMRun
  id
  task_name
  prompt_version
  provider
  model
  input_hash
  output_hash
  input_tokens nullable
  output_tokens nullable
  cost_usd nullable
  latency_ms nullable
  status
  error
  created_at
```

This helps with:
- cost tracking
- regression testing
- debugging
- prompt versioning
- avoiding duplicate calls

---

## Add strict validation helpers

Recommended module:

```text
app/llm/validation.py
```

Responsibilities:
- parse JSON
- validate enums
- clamp scores to 0.0-1.0
- enforce required fields
- report missing fields
- trigger JSON repair if needed

---

## Add prompt versioning

Every prompt output should include:

```json
{
  "schema_version": "1.0"
}
```

Every call should log:

```text
task_name
prompt_version
provider
model
input_hash
```

When prompt behavior changes materially, bump the prompt version.

---

## Add public/private output flags

Every generated text field should be treated as either:

```text
public_safe
private_internal
```

Public routes should only consume public-safe fields.

Private lead/collaboration fields should never be surfaced in public templates.

---

# Agent work packages

## Agent A — Prompt registry and loading

Owns:
- prompt file organization
- registry metadata
- prompt versioning
- template loading
- provider defaults

Acceptance:
- all prompt files load by name
- missing prompt produces clear error
- tests cover registry

---

## Agent B — Structured output validation

Owns:
- JSON parse
- JSON repair
- schema validation
- enum validation
- score clamping

Acceptance:
- malformed model output is repaired or rejected
- invalid enum is caught
- scores are clamped
- tests cover common failures

---

## Agent C — Funding prompts

Owns:
- funding extraction
- effort classification
- public funding card
- fixtures and evals

Acceptance:
- funding extraction works on at least three heterogeneous examples
- effort index matches expected examples
- public copy does not include private reasoning

---

## Agent D — Idea prompts

Owns:
- idea extraction
- idea public page synthesis
- duplicate/merge prompt support if needed

Acceptance:
- extracts useful non-generic ideas from persona snapshots
- avoids creating duplicate ideas for obvious synonyms
- public copy is exploratory and neutral

---

## Agent E — Matching prompts

Owns:
- entity-to-idea matching
- funding-to-entity matching
- hub-to-target matching

Acceptance:
- returns structured scores
- distinguishes strong, weak, and uncertain matches
- uses evidence-grounded rationale

---

## Agent F — Collaboration prompts

Owns:
- collaboration hypothesis
- outreach angle
- lead score explanation

Acceptance:
- creates concise private collaboration hypothesis
- produces practical recommended action
- does not create spammy outreach copy

---

# Recommended build order

1. Prompt registry
2. JSON validation and repair
3. Funding extraction prompt
4. Effort index prompt
5. Funding public card prompt
6. Idea extraction prompt
7. Entity-to-idea match prompt
8. Funding-to-entity match prompt
9. Hub-to-target match prompt
10. Collaboration hypothesis prompt
11. Outreach angle prompt

---

# Non-goals

For this phase, do not build:

- grant-writing automation
- automatic submission workflows
- eligibility guarantees
- financial compliance tooling
- detailed sponsor-specific schemas
- public lead scoring
- automated cold-email sending

Synapse should identify and explain meaningful research opportunities. It should not pretend to manage the full funding lifecycle.

