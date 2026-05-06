# Effort Index Specification

## Purpose

The Effort Index gives Synapse a simple, explainable way to describe the likely burden of pursuing a funding opportunity without trying to become a grant-management system.

Funding opportunities vary wildly across NIH, NSF, foundations, internal seed programs, nonprofit calls, corporate programs, and philanthropic sources. Some pages provide structured award information, while others provide only narrative text. The Effort Index should work across this uneven source material.

The goal is not to tell a researcher exactly how hard a submission will be. The goal is to help the Neurotech Hub and public users quickly distinguish between lightweight pilot opportunities, meaningful but manageable grants, and major heavy-lift mechanisms.

## Design principles

1. **Simple labels beat false precision.**
   Use a small number of labels: `mild`, `moderate`, `heavy`, and `unknown`.

2. **Effort is not quality.**
   A heavy opportunity may be strategically excellent. Effort should not directly suppress relevance or fit.

3. **Award amount is a strong signal, not the only signal.**
   Larger awards usually involve more work, but mechanism type, application structure, team expectations, institutional requirements, and deadline complexity also matter.

4. **Manual override is required.**
   The system can infer effort, but an admin should be able to correct it quickly.

5. **Store the rationale.**
   A label without an explanation is not useful. Every inferred Effort Index should include a short reason.

6. **Avoid brittle metadata requirements.**
   Do not require every funding opportunity to have amount, duration, eligibility, deadline, mechanism type, or application requirements. Store what is available and classify uncertainty honestly.

## Labels

### `mild`

A funding opportunity that appears relatively lightweight compared with typical federal or major foundation mechanisms.

Common signals:

- Small award amount
- Internal seed/pilot funding
- Short application
- Letter of intent, concept note, or brief proposal
- Travel, equipment, workshop, trainee, or small pilot support
- Single-PI or small-team submission
- Limited administrative complexity
- Short review timeline

Typical examples:

- Internal pilot award
- Departmental seed grant
- Small equipment supplement
- Travel or workshop award
- Small foundation pilot program

Public wording:

> Mild effort — likely a small or streamlined opportunity, but still requires a real submission.

### `moderate`

A funding opportunity that appears meaningful but manageable. These are often good candidates for Hub-supported collaboration planning.

Common signals:

- Mid-sized award
- Foundation research grant
- Pilot or exploratory external award
- Standard project proposal
- Some preliminary data or collaboration expectations
- Budget justification required
- Moderate eligibility constraints
- May require institutional submission but not a large center-scale effort

Typical examples:

- Foundation research award
- External pilot grant
- Small-to-mid NIH/NSF-style project mechanism
- Equipment or technology-development award with a real proposal
- Multi-investigator pilot with limited scope

Public wording:

> Moderate effort — likely requires a substantive proposal but may be realistic for a focused project or collaboration.

### `heavy`

A funding opportunity that appears to require substantial planning, administration, or collaboration.

Common signals:

- Large award amount
- Multi-year project
- Center, consortium, program project, cooperative agreement, or training program
- Multiple required investigators or institutions
- Detailed research strategy
- Complex budget or cost sharing
- Required institutional commitment
- Letter of intent plus full proposal
- Federal-scale submission
- Explicit milestones, management plans, data sharing plans, commercialization plans, or evaluation plans

Typical examples:

- NIH R01-scale or larger opportunities
- NSF center or major instrumentation opportunities
- Program project grants
- Multi-site consortium funding
- Large foundation initiatives
- Translational or commercialization programs with extensive milestones

Public wording:

> Heavy effort — likely a major proposal or multi-party submission that requires substantial planning.

### `unknown`

Use when the available evidence is insufficient or conflicting.

Common signals:

- No award amount
- No application description
- Dead link or inaccessible page
- Vague announcement
- Only a title or sponsor is available
- The page describes a funding program but not a specific opportunity

Public wording:

> Effort unknown — not enough information was available to estimate submission burden.

## Recommended score scale

The label is the primary user-facing object. The numeric score supports sorting, filtering, and downstream matching.

```text
unknown   = null or 0.50 with low confidence
mild      = 0.20
moderate  = 0.55
heavy     = 0.85
```

Use `null` when the opportunity truly cannot be classified. Use `0.50` only when a downstream system requires a numeric value.

Recommended fields:

```python
class FundingOpportunity(db.Model):
    effort_index = db.Column(db.String(32), default="unknown")
    effort_score = db.Column(db.Float, nullable=True)
    effort_confidence = db.Column(db.Float, nullable=True)
    effort_rationale = db.Column(db.Text, nullable=True)
    effort_signals_json = db.Column(db.JSON, nullable=True)
    effort_reviewed_at = db.Column(db.DateTime, nullable=True)
    effort_reviewed_by = db.Column(db.String(255), nullable=True)
```

## Signal hierarchy

The classifier should consider signals in this approximate order.

### 1. Mechanism type

Mechanism language is often more informative than amount.

Heavy indicators:

```text
center
consortium
program project
cooperative agreement
multi-site
institutional commitment
training program
large-scale
infrastructure
major instrumentation
phase II
commercialization
implementation network
```

Moderate indicators:

```text
research grant
pilot project
exploratory award
technology development
foundation award
equipment award
collaborative project
phase I
seed-to-scale
```

Mild indicators:

```text
seed grant
mini grant
travel award
workshop award
supplement
voucher
microgrant
concept note
letter of intent only
rapid pilot
internal pilot
```

### 2. Award amount

Suggested first-pass thresholds. These should be configurable.

```text
$0 - $25k        mild
$25k - $150k     mild to moderate
$150k - $500k    moderate
$500k - $1.5M    moderate to heavy
>$1.5M           heavy
```

Notes:

- Use total award amount when available.
- If only annual direct costs are available, infer total cautiously and store the assumption.
- If a funding page gives a broad range, use the upper bound as a burden signal but mention uncertainty.
- For equipment-only awards, amount may overstate writing burden but still indicates administrative burden.

### 3. Submission structure

Heavy indicators:

```text
letter of intent plus invited full proposal
multiple components
specific aims plus research strategy
management plan
evaluation plan
commercialization plan
data management and sharing plan
human subjects or animal protocol dependencies
institutional letter
cost sharing
milestone-driven budget
```

Moderate indicators:

```text
brief proposal
standard research plan
budget justification
biosketches
letters of support
preliminary data encouraged
```

Mild indicators:

```text
one-page proposal
short application
rolling review
simple online form
concept note
brief abstract
```

### 4. Team complexity

Heavy indicators:

```text
multi-PI required
multiple institutions required
community partners required
industry partner required
clinical partner required
center director required
advisory board required
```

Moderate indicators:

```text
collaboration encouraged
co-investigators allowed
cross-disciplinary team preferred
```

Mild indicators:

```text
single applicant
individual investigator
trainee applicant
small team
```

### 5. Deadline and timing

Effort and urgency are related but should be stored separately.

A near deadline does not make the grant intrinsically heavier, but it does make action harder. Use separate fields:

```python
deadline_urgency = "low|medium|high|expired|unknown"
days_until_deadline = int | None
```

Suggested urgency:

```text
expired                 expired
0 - 14 days             high
15 - 45 days            medium
46+ days                low
unknown deadline        unknown
```

## Effort versus match value

Do not compute lead value as `fit - effort`.

Instead, show these separately:

```text
Fit: high
Funding relevance: high
Effort: heavy
Timing: medium urgency
Strategic value: high
```

A heavy grant may be exactly the right opportunity if it aligns with a major Hub strategy. The better behavior is to create categories such as:

```text
Easy pilot
Good focused opportunity
Strategic heavy lift
Interesting but too soon
High fit, funding unclear
```

## Admin workflow

### Funding list view

Show columns:

```text
Title
Sponsor
Deadline
Amount
Effort
Confidence
Status
Public?
Reviewed?
```

Useful filters:

```text
Needs review
Active
Expired
Unknown effort
Heavy effort
Public
Private
High confidence
Low confidence
```

### Funding detail view

Show:

```text
Source URL
Fetched summary
Raw extracted amount/deadline text
Effort Index
Effort rationale
Signals used
Confidence
Admin override controls
```

Admin controls:

```text
Set effort: mild / moderate / heavy / unknown
Edit rationale
Mark reviewed
Mark public/private
Regenerate synthesis
Regenerate effort only
```

### Review policy

The public site may show an inferred Effort Index before review, but should distinguish reviewed from inferred internally.

Recommended public behavior:

```text
Show effort label if confidence >= 0.60.
If confidence < 0.60, show "Effort unknown" or "Estimated effort: unknown".
Never show confidence score publicly.
```

## Public UX

Public funding cards should stay lightweight.

Recommended card fields:

```text
Title
Sponsor
Deadline
Amount text
Effort label
Short public summary
Tags
External link
```

Example card copy:

```text
Effort: Moderate
A focused external award that likely requires a substantive proposal, budget, and clear project plan.
```

Avoid public wording that sounds judgmental:

Bad:

```text
This grant is hard.
This grant is not worth it.
This is too much work.
```

Better:

```text
This appears to be a heavy-lift opportunity.
This may require substantial planning or a multi-party proposal.
```

## Prompt: effort classifier

File:

```text
prompts/funding_effort_classify.txt
```

Suggested prompt:

```text
You classify the likely submission effort for a funding opportunity.

Return JSON only.

Use one of these effort_index values:
- mild
- moderate
- heavy
- unknown

Definitions:
- mild: likely a small or streamlined funding opportunity, such as a seed grant, pilot award, travel award, equipment supplement, short concept note, or small internal program.
- moderate: likely a substantive but manageable proposal, such as a foundation research award, external pilot grant, focused project grant, or technology-development award.
- heavy: likely a major proposal or multi-party submission, such as a large federal grant, center grant, consortium, program project, cooperative agreement, major instrumentation program, or multi-year high-budget opportunity.
- unknown: insufficient information.

Consider:
- award amount or amount range
- mechanism type
- duration
- required team structure
- application components
- institutional requirements
- cost sharing
- whether the opportunity appears internal, foundation, nonprofit, federal, corporate, or philanthropic

Important rules:
- Effort is not the same as strategic value.
- Do not penalize an opportunity for being heavy.
- If the page lacks evidence, return unknown.
- Be conservative with confidence.
- Do not invent requirements.

Return this JSON shape:
{
  "effort_index": "mild|moderate|heavy|unknown",
  "effort_score": 0.0,
  "confidence": 0.0,
  "rationale": "one short explanation",
  "signals": ["signal 1", "signal 2"],
  "amount_signal": "short text or null",
  "mechanism_signal": "short text or null",
  "team_signal": "short text or null",
  "application_signal": "short text or null",
  "missing_information": ["missing item 1"]
}

Funding page text:
{{ funding_text }}
```

## Prompt provider routing

### Use Ollama by default

Effort classification is a good local model task because:

- output is short
- schema is simple
- mistakes can be reviewed
- high volume may be expected
- most opportunities do not need expensive synthesis

Recommended environment variables:

```text
SYNAPSE_LLM_FUNDING_PROVIDER=ollama|openai|auto
SYNAPSE_LLM_FUNDING_FALLBACK_OPENAI=0|1
SYNAPSE_OLLAMA_FUNDING_MODEL=llama3.2
SYNAPSE_FUNDING_EFFORT_CONFIDENCE_MIN=0.60
```

### Use OpenAI selectively

OpenAI is useful when:

- Ollama fails to return valid JSON
- the page is long or structurally confusing
- the opportunity is marked high-value
- the admin clicks "Improve synthesis"
- batch matching requires high-quality reasoning
- public copy will be generated from messy source material

## Deterministic pre-classifier

Before using an LLM, Synapse can run a lightweight deterministic pass.

Inputs:

```text
amount_min
amount_max
amount_text
mechanism_text
deadline_text
raw_text
```

Outputs:

```text
candidate_effort_index
candidate_confidence
candidate_signals
```

Recommended use:

- If deterministic confidence is high, store the result and optionally skip LLM.
- If deterministic confidence is medium, pass signals into the LLM prompt.
- If deterministic confidence is low, rely on the LLM or mark unknown.

Example pseudo-code:

```python
def classify_effort_heuristic(funding):
    signals = []
    score = 0.5

    text = " ".join([
        funding.title or "",
        funding.amount_text or "",
        funding.raw_text or "",
    ]).lower()

    if any(term in text for term in ["center", "consortium", "program project", "cooperative agreement"]):
        signals.append("major mechanism language")
        score += 0.3

    if any(term in text for term in ["seed", "pilot", "travel", "microgrant", "mini grant"]):
        signals.append("streamlined mechanism language")
        score -= 0.25

    if funding.amount_max:
        if funding.amount_max >= 1_500_000:
            signals.append("large award amount")
            score += 0.3
        elif funding.amount_max >= 500_000:
            signals.append("substantial award amount")
            score += 0.15
        elif funding.amount_max <= 25_000:
            signals.append("small award amount")
            score -= 0.25

    if score >= 0.75:
        label = "heavy"
    elif score >= 0.40:
        label = "moderate"
    else:
        label = "mild"

    return label, min(max(score, 0.0), 1.0), signals
```

## Data quality and review flags

Recommended flags:

```python
needs_effort_review = confidence is None or confidence < 0.60
needs_amount_review = amount_text exists but amount_min/amount_max extraction failed
needs_deadline_review = deadline_text exists but deadline_date extraction failed
needs_public_review = public_summary exists but reviewed_at is null
```

## Tests

### Unit tests

Test deterministic classifier with examples:

```text
$5,000 travel award -> mild
$20,000 seed grant -> mild
$100,000 foundation pilot -> moderate
$300,000 technology-development award -> moderate
$2M center grant -> heavy
multi-site consortium with no amount -> heavy
no details -> unknown
```

### Prompt tests

Create small fixture pages:

```text
tests/fixtures/funding/mild_seed.txt
tests/fixtures/funding/moderate_foundation.txt
tests/fixtures/funding/heavy_center.txt
tests/fixtures/funding/unknown_sparse.txt
```

Expected behavior:

- valid JSON
- allowed label only
- confidence between 0 and 1
- rationale present
- does not invent amount or deadline
- uses `unknown` when evidence is sparse

### UI tests

Test:

- admin can override effort label
- reviewed timestamp updates
- low-confidence items show as needs review
- public card hides confidence score
- public card links to source URL

## Acceptance criteria

### MVP acceptance

- Funding opportunities can store an effort label, score, confidence, rationale, and signals.
- Admin can override effort manually.
- Public funding cards can display the effort label.
- Unknown effort is handled cleanly.
- No funding opportunity requires complete metadata.

### Synthesis acceptance

- A funding page can be classified from raw text.
- Ollama can produce valid JSON for common cases.
- OpenAI fallback can be enabled for failed or high-value cases.
- Classifier stores missing-information notes.
- Classifier does not collapse effort into match quality.

### Matching acceptance

- Funding matches can show both fit and effort.
- Heavy opportunities can still rank highly when strategically relevant.
- Lead/collaboration hypotheses can use effort to recommend an action style.

Example:

```text
High fit + mild effort:
  Suggest quick outreach or pilot.

High fit + moderate effort:
  Suggest scoped collaboration discussion.

High fit + heavy effort:
  Suggest strategic planning conversation, coalition building, or internal champion first.
```

## Future extensions

Potential later additions:

```text
time_to_apply_estimate
institutional_complexity
team_complexity
budget_complexity
proposal_complexity
review_cycle_complexity
hub_support_required
```

These should not be required for the MVP. Add them only if the simple Effort Index proves insufficient.
