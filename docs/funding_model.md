# Funding Model Spec

## Purpose

This document defines the first implementation slice for adding **Funding Opportunities** to Synapse.

Funding is the first new object required to turn Synapse from a research-intelligence/persona system into a research opportunity graph. The goal is not to become a grant-management platform. The goal is to collect enough structured and synthesized information to connect funding opportunities to people, organizations, places, ideas, Hub capabilities, and future collaboration hypotheses.

Funding records should be useful even when source pages are incomplete, inconsistent, or mostly unstructured.

---

## Design principles

1. **Keep metadata lightweight.** Funding sources vary widely across NIH, NSF, foundations, nonprofits, internal seed programs, philanthropic calls, and institutional opportunities.
2. **Prefer source links over exhaustive detail.** Public pages should summarize and point users to the official opportunity page.
3. **Make uncertainty visible.** Missing deadlines, unclear budgets, and ambiguous eligibility should be explicitly represented.
4. **Use an effort index, not a full grant-burden model.** The system only needs a useful estimate: `mild`, `moderate`, `heavy`, or `unknown`.
5. **Make all LLM output reviewable.** Operators should be able to override summaries, tags, deadlines, amounts, and effort index.
6. **Cache aggressively.** Funding pages should not be re-synthesized unless their content changes or an operator explicitly requests it.
7. **Separate public and private summaries.** Public content should be conservative and useful. Private content can include Hub-specific relevance.

---

## Scope

This spec covers:

- `FundingOpportunity` data model.
- Admin create/edit/review workflow.
- Public funding card behavior.
- Funding URL fetch and text extraction.
- LLM synthesis JSON.
- Effort index rules.
- Provider routing for Ollama vs. OpenAI.
- Validation and acceptance criteria.

This spec does **not** cover:

- Automated matching to people/orgs/ideas.
- Collaboration hypothesis generation.
- Full job queue architecture.
- Grant application management.
- User accounts or public saved searches.

Those belong to later docs.

---

## Core entity

### `FundingOpportunity`

Recommended SQLAlchemy model shape:

```python
class FundingOpportunity(db.Model):
    __tablename__ = "funding_opportunities"

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(300), nullable=False)
    slug = db.Column(db.String(320), nullable=True, index=True)

    sponsor_name = db.Column(db.String(200), nullable=True)
    source_url = db.Column(db.Text, nullable=False)
    normalized_source_url = db.Column(db.Text, nullable=True, index=True)
    source_type = db.Column(db.String(40), nullable=False, default="manual")

    status = db.Column(db.String(40), nullable=False, default="draft")
    is_public = db.Column(db.Boolean, nullable=False, default=False)

    deadline_date = db.Column(db.Date, nullable=True)
    deadline_text = db.Column(db.String(300), nullable=True)

    amount_min = db.Column(db.Integer, nullable=True)
    amount_max = db.Column(db.Integer, nullable=True)
    amount_text = db.Column(db.String(300), nullable=True)

    effort_index = db.Column(db.String(40), nullable=False, default="unknown")
    effort_score = db.Column(db.Float, nullable=True)
    effort_rationale = db.Column(db.Text, nullable=True)

    summary_public = db.Column(db.Text, nullable=True)
    summary_private = db.Column(db.Text, nullable=True)
    eligibility_summary = db.Column(db.Text, nullable=True)

    topic_tags_json = db.Column(db.JSON, nullable=True)
    method_tags_json = db.Column(db.JSON, nullable=True)
    hub_relevance_json = db.Column(db.JSON, nullable=True)

    raw_text = db.Column(db.Text, nullable=True)
    source_title = db.Column(db.String(300), nullable=True)
    content_hash = db.Column(db.String(64), nullable=True, index=True)
    synthesized_json = db.Column(db.JSON, nullable=True)

    synthesis_provider = db.Column(db.String(40), nullable=True)
    synthesis_model = db.Column(db.String(120), nullable=True)
    synthesis_prompt_version = db.Column(db.String(80), nullable=True)
    synthesis_confidence = db.Column(db.Float, nullable=True)
    synthesis_error = db.Column(db.Text, nullable=True)

    fetched_at = db.Column(db.DateTime, nullable=True)
    synthesized_at = db.Column(db.DateTime, nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
```

### Required fields

Only these should be strictly required:

```text
title
source_url
source_type
status
is_public
effort_index
created_at
updated_at
```

Everything else should tolerate missing or uncertain data.

---

## Field conventions

### `status`

Allowed values:

```text
draft
active
expired
archived
```

Suggested meanings:

| Status | Meaning |
|---|---|
| `draft` | Created or synthesized but not reviewed. |
| `active` | Reviewed and currently relevant. |
| `expired` | Deadline has passed or opportunity is no longer available. |
| `archived` | Hidden from normal workflows but preserved. |

### `source_type`

Allowed values:

```text
manual
url_fetch
rss
public_search
imported
```

Initial implementation can support only `manual` and `url_fetch`.

### `is_public`

Controls whether a funding opportunity appears on the public site.

Do not assume that `status == active` means public. Operators should explicitly publish.

### `deadline_date` and `deadline_text`

Use both.

- `deadline_date` supports sorting and deadline flags.
- `deadline_text` preserves source ambiguity such as “rolling,” “LOI due in March,” or “anticipated deadline.”

When the model is uncertain, leave `deadline_date = null` and preserve the original phrase in `deadline_text`.

### `amount_min`, `amount_max`, and `amount_text`

Use all three.

- `amount_text` is the source-of-truth human-readable value.
- `amount_min` and `amount_max` are optional parsed numeric aids.
- Do not force parsing when the source text is ambiguous.

Examples:

| Source text | Parsed |
|---|---|
| `$50,000 pilot award` | `amount_min=50000`, `amount_max=50000`, `amount_text="$50,000 pilot award"` |
| `up to $250,000 over two years` | `amount_min=null`, `amount_max=250000`, `amount_text="up to $250,000 over two years"` |
| `amount varies` | `amount_min=null`, `amount_max=null`, `amount_text="amount varies"` |

---

## Effort index

### Allowed values

```text
mild
moderate
heavy
unknown
```

There is intentionally no `none` category. Even small funding mechanisms require effort.

### Meaning

| Effort | Score | Meaning |
|---|---:|---|
| `mild` | `0.25` | Smaller seed grants, short applications, travel/equipment supplements, internal pilots, low coordination burden. |
| `moderate` | `0.55` | Foundation awards, pilot grants, moderate budgets, standard narratives, some collaboration or institutional review. |
| `heavy` | `0.85` | NIH/NSF-scale mechanisms, center grants, large multi-year awards, multi-PI submissions, complex institutional requirements. |
| `unknown` | `null` | Insufficient evidence. |

### Important interpretation

Effort is not a negative score.

A heavy opportunity may be strategically excellent. Effort should guide planning, not suppress opportunity discovery.

Later matching should keep these separate:

```text
fit_score
effort_index
deadline_urgency
strategic_value
```

### Initial heuristic rules

The effort classifier should consider available evidence only.

Signals for `mild`:

- small award amount, often under roughly `$25k-$75k`
- internal seed/pilot program
- travel, equipment, workshop, or supplement language
- short application
- rolling or frequent cycles
- single PI or small team

Signals for `moderate`:

- award amount roughly `$75k-$500k`
- foundation or society award
- pilot project with narrative and budget
- letter of intent plus invited proposal
- collaboration encouraged but not structurally complex
- institutional approval likely but not unusually burdensome

Signals for `heavy`:

- NIH/NSF major mechanism language
- center, consortium, program project, cooperative agreement, training grant, limited submission
- multi-PI, multi-site, or institutional commitment
- cost sharing
- complex budget or subaward structure
- award amount above roughly `$500k`
- long duration, often 3+ years

Signals for `unknown`:

- no amount
- no mechanism type
- source page is only a landing page
- eligibility and application format are unclear
- extracted text is too short or low confidence

### Suggested deterministic fallback

Before or after LLM synthesis, a simple fallback can classify obvious cases:

```python
def effort_from_amount(amount_max: int | None) -> tuple[str, float | None]:
    if amount_max is None:
        return "unknown", None
    if amount_max < 75_000:
        return "mild", 0.25
    if amount_max < 500_000:
        return "moderate", 0.55
    return "heavy", 0.85
```

Do not rely on amount alone when better evidence is available.

---

## Admin workflow

## Phase 1: manual funding MVP

### Funding list

Admin route:

```text
/admin/funding/
```

List columns:

```text
Title
Sponsor
Deadline
Amount
Effort
Status
Public?
Updated
```

Filters:

```text
status
effort_index
is_public
sponsor_name
has_deadline
expired/upcoming
```

### Add funding opportunity

Admin route:

```text
/admin/funding/new
```

Minimum form fields:

```text
Title
Source URL
Sponsor
Deadline text
Deadline date
Amount text
Amount min
Amount max
Effort index
Effort rationale
Public summary
Private summary
Eligibility summary
Status
Public toggle
Topic tags
Method tags
```

### Funding detail/review

Admin route:

```text
/admin/funding/<id>
```

Show:

- source link
- public/private state
- structured metadata
- public summary preview
- private summary
- effort index and rationale
- synthesis confidence, if present
- raw extracted text, collapsed
- synthesized JSON, collapsed
- review actions

Actions:

```text
Edit
Mark reviewed
Publish / unpublish
Archive
Delete, optional and protected
```

---

## Phase 2: URL synthesis workflow

### Fetch and synthesize

Admin action:

```text
/admin/funding/fetch
```

Input:

```text
URL
optional operator notes
```

Flow:

```text
1. Normalize URL.
2. Fetch page.
3. Extract readable text.
4. Compute content hash.
5. If same URL/hash already exists, offer to open existing record.
6. Run funding synthesis if new or explicitly requested.
7. Save as draft.
8. Present review screen.
```

### Re-synthesize

Admin action:

```text
/admin/funding/<id>/resynthesize
```

Options:

```text
Use cached raw text
Re-fetch URL first
Prefer Ollama
Prefer OpenAI
```

Default should be:

```text
Re-fetch URL first: false
Provider: default funding provider
```

---

## Public UI

Public route options:

```text
/funding/
/funding/<slug>
```

Public funding cards should show:

```text
Title
Sponsor
Short public summary
Deadline text/date
Amount text
Effort index
Topic tags
Method tags
Official source link
```

Public detail pages can add:

```text
Eligibility summary
Related ideas, later phase
Related organizations, later phase
Related Hub capabilities, later phase
```

Public pages should not show:

```text
private summary
internal match scores
lead score
inferred pain points
outreach recommendations
operator notes
raw LLM JSON
```

Suggested public language near funding cards:

```text
Funding summaries are simplified for discovery. The official opportunity page is the source of truth.
```

---

## URL fetch and text extraction

Suggested files:

```text
app/funding/
  __init__.py
  fetch.py
  extract.py
  synthesize.py
  effort.py
  forms.py
  routes.py
```

### Fetch behavior

`fetch.py` should:

- accept a URL
- normalize the URL
- use a reasonable timeout
- follow redirects
- reject non-HTTP(S) schemes
- capture final URL
- capture response status
- capture content type
- return clear errors

### Extraction behavior

`extract.py` should:

- strip scripts, styles, nav, footer where possible
- preserve title and headings
- produce readable text
- cap extracted text length
- compute SHA-256 hash of normalized extracted text

Suggested return shape:

```python
@dataclass
class FundingPageText:
    url: str
    final_url: str
    status_code: int
    content_type: str | None
    title: str | None
    text: str
    content_hash: str
    fetched_at: datetime
```

### Text caps

Initial defaults:

```text
SYNAPSE_FUNDING_FETCH_TIMEOUT_SEC=20
SYNAPSE_FUNDING_EXTRACT_MAX_CHARS=60000
SYNAPSE_FUNDING_PROMPT_MAX_CHARS=24000
```

The raw extracted text can be longer than the prompt text, but both should be capped.

---

## LLM synthesis

Prompt file:

```text
prompts/funding_extract.txt
```

Prompt version:

```text
funding_extract_v1
```

### Input

The prompt should receive:

```text
URL
page title
operator notes, optional
extracted text, capped
current date
```

### Output JSON

Required JSON shape:

```json
{
  "title": "",
  "sponsor": "",
  "one_sentence_summary": "",
  "public_summary": "",
  "private_summary": "",
  "eligibility_summary": "",
  "who_should_care": [],
  "eligible_entities": [],
  "topic_tags": [],
  "method_tags": [],
  "possible_hub_relevance": [],
  "amount_text": "",
  "amount_min": null,
  "amount_max": null,
  "deadline_text": "",
  "deadline_date": null,
  "effort_index": "unknown",
  "effort_score": null,
  "effort_rationale": "",
  "confidence": 0.0,
  "missing_information": [],
  "source_warnings": []
}
```

### Output rules

The model must:

- return strict JSON only
- preserve uncertainty
- use `null` for unknown parsed values
- preserve original amount/deadline phrases where possible
- avoid inventing exact dates or amounts
- avoid making eligibility claims not supported by the text
- keep public summaries conservative
- keep Hub-specific interpretation in private fields
- classify effort as `mild`, `moderate`, `heavy`, or `unknown`
- include confidence from `0.0` to `1.0`

### Suggested prompt text

```text
You are extracting a lightweight funding opportunity record for a research intelligence system.

Use only the provided page text and operator notes. Do not invent missing amounts, deadlines, eligibility, or sponsor details. If information is unclear, use null, an empty list, or "unknown".

Return strict JSON matching the requested schema.

Classify effort_index as one of: mild, moderate, heavy, unknown.
There is no "none" effort category.
Effort means likely application and coordination burden, not scientific value.

Public summaries should be conservative and should refer users to the official source link for details.
Private summaries may mention possible relevance to a neuroscience/neurotechnology technical services hub.
```

---

## Provider routing

### Defaults

```text
Funding extraction: Ollama
Effort classification: Ollama
Fallback/escalation: OpenAI
```

### Suggested environment variables

```text
SYNAPSE_LLM_FUNDING_PROVIDER=ollama|openai|auto
SYNAPSE_LLM_FUNDING_FALLBACK_OPENAI=1
SYNAPSE_OPENAI_FUNDING_MODEL=gpt-4o-mini
SYNAPSE_OPENAI_FUNDING_TIMEOUT_SEC=45
SYNAPSE_OLLAMA_FUNDING_MODEL=<defaults to OLLAMA_MODEL>
SYNAPSE_OLLAMA_FUNDING_TIMEOUT_SEC=90
SYNAPSE_FUNDING_PROMPT_MAX_CHARS=24000
SYNAPSE_FUNDING_LOW_CONFIDENCE_THRESHOLD=0.55
```

### Escalate to OpenAI when

- Ollama returns malformed JSON.
- JSON validates but confidence is below threshold.
- Extracted page is long, complex, or highly structured.
- Opportunity is manually marked high-value.
- Operator explicitly chooses OpenAI.

### Stay on Ollama when

- Routine funding extraction.
- Low-stakes opportunities.
- Batch processing.
- Re-running unchanged or low-value records.
- Generating internal drafts.

### Store provider metadata

Every synthesis should record:

```text
provider
model
prompt_version
confidence
error, if any
synthesized_at
```

---

## Validation

### JSON validation

Create a lightweight validator for synthesis output.

Required checks:

- output is valid JSON object
- `effort_index` is one of allowed values
- `effort_score` is null or `0.0-1.0`
- `confidence` is `0.0-1.0`
- `topic_tags`, `method_tags`, `who_should_care`, `eligible_entities`, `possible_hub_relevance`, `missing_information`, and `source_warnings` are lists
- `deadline_date` is null or ISO date string
- `amount_min` and `amount_max` are null or integers

### Repair behavior

Initial repair strategy:

1. Try normal JSON parse.
2. Try extracting the first JSON object from the response.
3. Try local deterministic repair for common issues.
4. If still invalid, mark synthesis failed.
5. If fallback enabled, retry with OpenAI.

Do not silently publish invalid synthesis.

---

## Tagging conventions

Tags should be short, lowercase where practical, and reusable.

Example topic tags:

```text
neurotechnology
behavior
electrophysiology
brain-machine interface
computational neuroscience
preclinical models
translation
training
instrumentation
```

Example method tags:

```text
in vivo electrophysiology
closed-loop stimulation
behavioral tracking
wireless devices
home-cage monitoring
machine learning
optogenetics
calcium imaging
implantable devices
microfabrication
```

Avoid creating overly specific one-off tags unless needed.

---

## Expiration and deadline behavior

Initial behavior can be simple:

```text
If deadline_date is in the past and status is active, show "deadline passed" warning in admin.
Do not automatically archive in Phase 1.
```

Later automation may:

- mark `expired`
- notify operators before deadlines
- re-check pages for updated cycles
- create recurring funding templates

---

## Security and safety notes

- Fetch only HTTP(S) URLs.
- Set timeouts.
- Limit response size.
- Do not execute page scripts.
- Do not expose raw extracted text publicly unless explicitly reviewed.
- Treat LLM output as untrusted until validated.
- Public summaries should not imply endorsement or guaranteed eligibility.

---

## Tests

### Model tests

- Can create a minimal funding opportunity with only required fields.
- Missing deadline and amount fields are allowed.
- Invalid effort index is rejected or normalized.
- Status values are constrained.
- Public visibility is independent of status.

### Fetch/extract tests

- Rejects non-HTTP URLs.
- Handles redirects.
- Handles timeout error.
- Extracts title and readable text from sample HTML.
- Computes stable content hash.

### Synthesis validation tests

- Accepts valid JSON.
- Rejects invalid effort index.
- Rejects confidence outside `0.0-1.0`.
- Accepts null deadline and amount.
- Handles malformed JSON failure.

### Admin route tests

- Admin can create funding manually.
- Admin can edit funding.
- Admin can archive funding.
- Admin can publish/unpublish funding.
- Public page only shows `is_public=True` records.

---

## Acceptance criteria

## Phase 1 acceptance criteria

- `FundingOpportunity` model and migration exist.
- Admin can create/edit/archive funding opportunities.
- Funding records tolerate missing amount, deadline, sponsor, and eligibility fields.
- Effort index can be manually set.
- Public visibility is operator-controlled.
- Public funding list is optional but, if present, shows only public records.
- Existing persona, ingestion, and lead report flows are unaffected.

## Phase 2 acceptance criteria

- Admin can paste a URL and fetch readable text.
- System computes and stores content hash.
- System can synthesize funding metadata into reviewable JSON.
- Effort index is generated and editable.
- Malformed or incomplete pages fail gracefully.
- Provider, model, prompt version, confidence, and errors are recorded.
- Public cards avoid unsupported detail and link to the official source.

---

## Agent implementation checklist

## Agent A — Data model

- Add `FundingOpportunity` model.
- Add migration.
- Add allowed-value helpers/constants.
- Add model tests.
- Add slug helper, if public detail pages are implemented.

## Agent B — Admin UI

- Add Admin → Funding navigation.
- Add funding list.
- Add create/edit forms.
- Add detail/review page.
- Add publish/unpublish/archive actions.

## Agent C — Funding fetch/extract

- Add URL normalization.
- Add safe fetch helper.
- Add readable text extraction.
- Add content hashing.
- Add error handling.

## Agent D — Funding synthesis

- Add `prompts/funding_extract.txt`.
- Add synthesis service.
- Add JSON validation.
- Add Ollama/OpenAI routing.
- Add fallback behavior.
- Store provider metadata.

## Agent E — Public UI

- Add public funding list, if included in current milestone.
- Add public funding detail page, if included.
- Ensure only public records appear.
- Add official source link.

---

## Recommended first milestone

Build this first without LLM synthesis:

```text
1. Model + migration.
2. Admin CRUD.
3. Manual effort index.
4. Manual public/private summaries.
5. Public visibility flag.
6. Basic tests.
```

Then add URL fetch and LLM synthesis as the second milestone.

This keeps the system useful immediately and prevents the LLM workflow from blocking the schema/UI foundation.
