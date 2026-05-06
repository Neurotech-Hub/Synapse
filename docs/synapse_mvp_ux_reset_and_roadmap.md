# Synapse MVP UX Reset and Roadmap

## Purpose

Synapse has gained powerful backend capabilities quickly. That is good for proving the research-intelligence architecture, but the admin and public experiences are becoming too dense.

This document resets the vision around a simpler MVP:

> Synapse should help the Neurotech Hub turn messy research evidence into a small number of trusted, useful outputs.

Those outputs should support:

```text
1. Internal lead generation
2. Public discovery
3. Funding-aware collaboration planning
4. A fun, curated, exploratory public experience
```

The immediate priority is not more capability. The priority is making the existing capability understandable.

---

# Current Problem

The backend admin area now exposes too many low-level controls.

Example funding actions currently include:

```text
Mark reviewed
Rebuild effort
Fetch source text
Synthesize draft
Regenerate public card
Generate matches
Archive
```

Each action is individually useful, but together they force the operator to understand the implementation pipeline.

The public site has the same pattern. Navigation has become database-like:

```text
Home
Explore
People
Organizations
Ideas
Funding
Search
```

That reflects the app's tables, not the intended public experience.

The product should not feel like:

```text
a database with LLM buttons
```

It should feel like:

```text
a simple research intelligence cockpit that produces curated outputs
```

---

# Updated Product Vision

## One-sentence vision

Synapse is a research opportunity engine for the Neurotech Hub.

It ingests evidence, extracts useful signals, connects people, organizations, ideas, places, and funding, and turns those connections into curated public discovery and private collaboration opportunities.

## Admin promise

For operators:

> Give Synapse sources and funding opportunities. Synapse helps you review signals, identify meaningful connections, and produce collaboration hypotheses.

## Public promise

For visitors:

> Explore a curated atlas of neuroscience technology: ideas, opportunities, people, organizations, places, and funding signals connected by meaningful research themes.

## Lead-generation promise

For the Hub:

> Find the right people and organizations to engage, understand why they matter, and identify what funding or project angle could make the collaboration real.

---

# Product Principle Reset

## Principle 1 — Admin should expose outputs, not machinery

Most users should not need to know whether the system is fetching, synthesizing, rebuilding, regenerating, matching, or validating.

The default admin question should be:

```text
What needs my attention?
```

Not:

```text
Which backend operation should I run?
```

## Principle 2 — Hide advanced controls until needed

The current controls are useful for testing and debugging. Keep them, but move them behind an advanced panel.

Recommended pattern:

```text
Primary action
Secondary action
Advanced actions
Diagnostics
```

## Principle 3 — Every object should have one obvious next action

For each admin object, show one recommended action:

```text
Funding: Review funding card
Idea suggestion: Accept, merge, or reject
Match: Review relationship
Hypothesis: Approve next action
LLMRun failure: Inspect error
```

## Principle 4 — Public UX should be story-first, not table-first

The public site should not expose every entity type as a top-level nav item.

The public site should guide people through:

```text
What is happening?
What ideas are emerging?
Who is connected?
What opportunities exist?
How can the Hub help?
```

## Principle 5 — MVP means fewer workflows, better flows

Do not add more objects or dashboards until the core flows feel obvious.

---

# What to Tone Down From Sprints 01–03

Sprints 01–03 are technically complete and valuable. They should not be undone. But the UX should be simplified before Sprint 04 continues too far.

The review confirms that Sprints 01–03 completed funding review, ContentItem-derived Idea suggestions, manual relationships, selected-match rationales, and preserved public/LLM safety boundaries. It also notes that many items were intentionally kept thin to avoid broadening the implementation. That was the right technical call, but the resulting admin surface now needs an operator-facing simplification pass.

## Funding

### Keep

```text
field-by-field review
fetch source text
synthesize draft
regenerate public card
rebuild effort
generate matches
archive
LLMRun diagnostics
fetch diagnostics
```

### Tone down

Do not show all actions as equal top-level buttons.

Replace the button row with a staged workflow:

```text
Step 1: Source
Step 2: Draft
Step 3: Public Card
Step 4: Relationships
Step 5: Publish
```

### Recommended simple UI

At top of Funding detail:

```text
Status card:
  Needs source text / Draft ready / Ready to publish / Published

Primary button:
  Continue review

Secondary:
  Preview public card

Advanced:
  Fetch source text
  Rebuild effort
  Synthesize draft
  Regenerate public card
  Generate matches
  Clear fetch error
  View LLM runs
  Archive
```

### Simple mental model

Funding admin should feel like:

```text
Can this funding opportunity become a useful public card and/or lead-generation signal?
```

Not:

```text
Which model operation do I run?
```

---

## Ideas

### Keep

```text
manual Ideas
ContentItem suggestions
PersonaSnapshot suggestions
accept/reject/merge
duplicate detection
public/private gating
```

### Tone down

Do not make operators manage Ideas like a database.

Idea review should be framed as:

```text
Is this a useful research theme?
```

Recommended queues:

```text
Suggested Ideas
Published Ideas
Archived Ideas
```

### Recommended simple UI

For each suggested Idea:

```text
Idea title
Why Synapse suggested it
Evidence snippet
Related source
Possible duplicate
Actions:
  Accept
  Merge
  Reject
```

Hide LLM/provider diagnostics behind details.

---

## Matching / Relationships

### Keep

```text
manual relationship editor
MatchEdge detail page
accept/reject/archive
private/public-safe visibility
LLM rationale for selected match
```

### Tone down

Do not make matching feel like graph database administration.

Frame it as:

```text
Relationships to review
```

Recommended display:

```text
Connection:
  Idea ↔ Person
Why it matters:
  short rationale
Evidence:
  1-2 snippets
Actions:
  Accept
  Keep private
  Make public-safe
  Reject
```

Move score, MatchRun, LLMRun, JSON details, and raw features into an advanced section.

---

## Public Site

### Keep

```text
Home
Explore
Search
public Idea pages
public Funding pages
public people/org pages
public-safe cross-links
```

### Tone down

Remove most entity-specific top-level nav items.

Current top-level nav is too database-like:

```text
Home
Explore
People
Organizations
Ideas
Funding
Search
```

Recommended MVP nav:

```text
Home
Explore
Opportunities
Work with the Hub
Search
```

Alternative even simpler:

```text
Home
Atlas
Opportunities
Work with Us
```

Entity lists can still exist, but they should be discovered inside Explore/Search, not top-level navigation.

---

# MVP Output Model

To simplify both admin and public UX, define the core outputs explicitly.

## Output 1 — Public Card

A reviewed public-facing object.

Examples:

```text
Funding card
Idea card
Person card
Organization card
Place card
Latest signal card
```

A public card has:

```text
title
short summary
tags
source link where relevant
related public-safe cards
visibility/review status
```

## Output 2 — Relationship

A reviewed connection between two objects.

Examples:

```text
Idea ↔ Funding
Idea ↔ Person
Idea ↔ Organization
Funding ↔ Person
Organization ↔ Place
```

A relationship has:

```text
private rationale
optional public-safe summary
status
visibility
evidence
```

## Output 3 — Collaboration Hypothesis

A private lead-generation output.

A hypothesis has:

```text
target
why now
supporting evidence
related Ideas
related Funding
Hub fit
effort/timing
recommended next action
status
priority
```

## Output 4 — Review Item

An admin task.

Examples:

```text
Funding needs review
Idea suggestion needs decision
Relationship needs review
Hypothesis needs approval
LLM run failed
```

The admin homepage should be built around Review Items, not database objects.

---

# Simplified Admin Information Architecture

## Recommended admin nav for MVP

```text
Dashboard
Review
Opportunities
Atlas
Leads
Sources
Settings
```

### Dashboard

Purpose:

```text
What changed?
What needs attention?
What is ready?
```

Shows:

```text
review queue counts
recent high-value funding
new Idea suggestions
pending relationships
draft hypotheses
failed LLM/fetch items
```

### Review

Purpose:

```text
One place to clear pending work.
```

Sections:

```text
Funding to review
Idea suggestions
Relationships
Draft hypotheses
System issues
```

### Opportunities

Purpose:

```text
Manage funding and fundable opportunities.
```

Includes:

```text
Funding
Funding import
Funding review
Funding public cards
```

Do not expose every funding operation as primary.

### Atlas

Purpose:

```text
Manage public discovery objects.
```

Includes:

```text
Ideas
People
Organizations
Places
Public cards
Public-safe relationships
```

### Leads

Purpose:

```text
Manage private collaboration hypotheses.
```

Includes:

```text
Collaboration hypotheses
Lead reports
Target watchlist
Prioritized opportunities
```

### Sources

Purpose:

```text
Manage inputs.
```

Includes:

```text
Sources
ContentItems
RSS/HTML polling
Submitted URLs
Persona snapshots
```

### Settings

Purpose:

```text
Control risk and system behavior.
```

Includes:

```text
LLM settings
feature flags
provider status
caps
diagnostics
advanced controls
```

---

# Simplified Funding Workflow

## Current issue

Funding detail exposes all backend operations at once.

## New MVP workflow

### Funding status states

Use a simple state label:

```text
Needs source
Needs synthesis
Needs review
Ready to publish
Published
Archived
```

### Top-level Funding detail actions

Only show 1–3 top-level actions:

```text
Continue review
Preview public card
Publish / Mark public
```

### Advanced actions

Collapse these into an Advanced Tools panel:

```text
Fetch source text
Synthesize draft
Regenerate public card
Rebuild effort
Generate matches
Clear fetch error
View LLM runs
Archive
```

### Suggested button logic

If no raw text:

```text
Primary: Fetch source
Secondary: Edit manually
```

If raw text but no synthesis draft:

```text
Primary: Generate draft
Secondary: Edit manually
```

If synthesis draft exists:

```text
Primary: Review draft
Secondary: Discard draft
```

If reviewed but not public:

```text
Primary: Publish card
Secondary: Generate relationships
```

If public:

```text
Primary: Preview public page
Secondary: Review relationships
```

### Admin copy

Use plain language:

```text
Fetch source text
```

can become:

```text
Read from source link
```

```text
Synthesize draft
```

can become:

```text
Create review draft
```

```text
Regenerate public card
```

can become:

```text
Rewrite public summary
```

```text
Generate matches
```

can become:

```text
Find related Ideas and people
```

---

# Simplified Public Information Architecture

## Current issue

Public nav exposes object classes directly.

## Recommended MVP public nav

```text
Home
Explore
Opportunities
Work with the Hub
Search
```

### Home

Purpose:

```text
Explain what the Neurotech Hub is and why this atlas exists.
```

Sections:

```text
Hero
Featured Ideas
Funding Radar preview
Latest signals
How the Hub helps
CTA: Work with the Hub
```

### Explore

Purpose:

```text
A guided atlas.
```

Sections:

```text
Explore by Idea
Explore by Research Area
Explore by Method
Explore by Organization
Explore by Place
```

People/orgs/funding are discoverable here, not necessarily top-level nav.

### Opportunities

Purpose:

```text
Funding and buildable collaboration opportunities.
```

Sections:

```text
Funding Radar
Buildable Ideas
Active opportunity themes
```

This can include funding without making “Funding” the user-facing nav concept.

### Work with the Hub

Purpose:

```text
Convert interest into action.
```

Sections:

```text
Request support
Submit a project idea
Submit a URL/resource
Contact
What the Hub can build
```

### Search

Purpose:

```text
Find a person, organization, idea, funding opportunity, or signal.
```

Search remains useful, but it should not replace guided exploration.

---

# Public Site Tone

The public site should not say:

```text
Browse our database of people, organizations, ideas, and funding.
```

It should feel like:

```text
Explore emerging neuroscience technology opportunities.
```

Possible language:

```text
A living atlas of neuroscience technology, funding signals, and collaboration opportunities.
```

```text
Discover ideas, tools, people, and opportunities shaping the next generation of neuroscience.
```

```text
Where research signals become buildable collaborations.
```

---

# MVP User Testing Goal

The goal of MVP user testing is not to validate every backend feature.

The goal is to test whether users understand and value the outputs.

## Admin testing questions

Ask operators:

```text
Can you tell what needs review?
Do you know the next action for each object?
Do you trust the generated summary?
Can you tell what will be public?
Can you tell what remains private?
Can you find the relationship between funding, ideas, and leads?
```

## Public testing questions

Ask visitors:

```text
Do you understand what this site is?
Does Explore feel useful?
Can you find interesting Ideas or opportunities?
Do the connections feel meaningful?
Do you understand how the Hub can help?
Would you submit a project, URL, or request?
```

## Lead-generation testing questions

Ask Hub stakeholders:

```text
Does the hypothesis identify a plausible collaboration?
Is the evidence convincing?
Is the recommended action useful?
Does funding context change prioritization?
Would you act on this?
```

---

# Roadmap Toward MVP User Testing

## Phase 0 — UX Simplification Pass

Goal:

```text
Reduce admin and public cognitive load before adding more capability.
```

Scope:

```text
simplify admin nav
create Review-first admin dashboard
collapse advanced actions
rename technical actions into operator language
simplify public nav
convert public nav from entity-first to experience-first
```

Deliverables:

```text
admin information architecture update
public nav update
Funding detail simplification
Review queue emphasis
Advanced Tools panels
copy cleanup
```

This should happen before or alongside Sprint 04.

---

## Phase 1 — Collaboration Hypotheses MVP

Goal:

```text
Make private lead-generation outputs useful.
```

Scope:

```text
target-centered hypotheses for Person and Organization
multiple accepted relationships
related Ideas
related Funding
effort/timing
Hub capability context
recent evidence
recommended next action
review/edit/status workflow
```

Deliverable:

```text
A Hub operator can open Leads and see actionable collaboration hypotheses.
```

---

## Phase 2 — Public Atlas MVP

Goal:

```text
Make the public site feel curated and exploratory.
```

Scope:

```text
simplified public nav
Explore as primary discovery surface
Opportunities page
Work with the Hub page
related cards/chips
Homepage refresh
```

Deliverable:

```text
A visitor can understand the site, explore meaningful themes, and find a path to engage the Hub.
```

---

## Phase 3 — Admin Review MVP

Goal:

```text
Make the backend manageable.
```

Scope:

```text
Review dashboard
review queue filters
object status cards
one recommended action per object
bulk low-risk actions
clear public/private indicators
advanced tools collapsed
```

Deliverable:

```text
An operator can clear daily review tasks without understanding the full backend pipeline.
```

---

## Phase 4 — User Testing Prep

Goal:

```text
Prepare for real feedback.
```

Scope:

```text
seed realistic funding examples
seed realistic Ideas
seed public-safe relationships
seed 5-10 collaboration hypotheses
write admin test script
write public visitor test script
write stakeholder lead-gen test script
fix obvious confusing labels
```

Deliverable:

```text
A testable MVP with representative content and guided test tasks.
```

---

# Recommended Immediate Sprint

## Sprint 04A — UX Simplification Before More Features

This should happen before the Collaboration Hypotheses sprint or as a short pre-sprint.

### Goal

Make the current backend and public site easier to understand.

### Scope

```text
1. Simplify public nav
2. Simplify admin nav labels/grouping
3. Collapse funding advanced actions
4. Add one primary recommended action to Funding detail
5. Rename technical buttons into operator language
6. Improve Review dashboard prominence
7. Add clear public/private status badges
```

### Out of scope

```text
new models
new LLM prompts
new matching logic
new hypothesis generation
public graph visualization
persistent settings
```

### Success criteria

```text
Funding detail no longer presents 7 equal top-level buttons.
Admin can identify the next recommended action.
Advanced/debug operations remain available but collapsed.
Public nav no longer exposes every entity table.
Explore/Opportunities/Work with the Hub become the public mental model.
Existing tests still pass.
```

---

# Recommended Next Sprints After 04A

## Sprint 04B — Collaboration Hypotheses MVP

Build the strategic private output.

## Sprint 05 — Public Atlas MVP

Make the public site coherent and user-testable.

## Sprint 06 — Admin Review MVP

Make ongoing operation manageable.

## Sprint 07 — Seed and User Testing Prep

Prepare representative content and testing scripts.

---

# Final Recommendation

Do not continue directly into more backend capability until the UX is simplified.

The current system has enough machinery. The next move should be:

```text
Make Synapse feel simple.
```

Then use that simplified frame to finish the MVP:

```text
Admin:
  Review signals → approve public cards → approve relationships → act on hypotheses

Public:
  Explore ideas → discover opportunities → understand Hub capabilities → engage

Lead generation:
  Review evidence-grounded hypotheses → prioritize → contact or defer
```

This reset does not discard the work from Sprints 01–03. It packages it into a clearer product.
