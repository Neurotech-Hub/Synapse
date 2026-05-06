# Sprint 04A — UX Simplification Before More Features

## Primary Reference

Read this for product direction:

```text
docs/synapse_mvp_ux_reset_and_roadmap.md
```

But implement only the scope in this sprint.

## Sprint Goal

Make Synapse feel simpler before adding more backend capability.

The app now has many useful systems:

```text
Funding review
Funding synthesis
Effort index
Ideas
Idea suggestions
Relationships
Match rationales
Public Funding/Ideas
Explore/Search
LLM logging
Settings
Review queues
```

But the admin and public UI are starting to expose the internal machinery too directly.

This sprint should reduce cognitive load by reframing the UX around clear outputs and obvious next actions.

The goal is not to remove advanced capability. The goal is to hide advanced operations until needed.

---

## Product Direction

Synapse should not feel like:

```text
a database with LLM buttons
```

It should feel like:

```text
a research intelligence cockpit that produces curated outputs
```

Admin users should understand:

```text
what needs review
what is public
what is private
what the next action is
what advanced/debug controls are available if needed
```

Public users should experience:

```text
a curated research atlas
```

not:

```text
a list of database tables
```

---

# In Scope

## 1. Simplify Public Navigation

Current public navigation is too entity/table-oriented:

```text
Home
Explore
People
Organizations
Ideas
Funding
Search
```

Replace with a simpler experience-oriented nav.

Recommended MVP nav:

```text
Home
Explore
Opportunities
Work with the Hub
Search
```

Alternative acceptable nav:

```text
Home
Atlas
Opportunities
Work with Us
Search
```

Entity pages should still exist, but they should not all be top-level navigation items.

### Expected behavior

Keep routes such as:

```text
/people/
/organizations/
/ideas/
/funding/
```

if they already exist.

But make them discoverable through:

```text
Explore
Search
Opportunities
related cards/chips
```

rather than top-level tabs.

---

## 2. Simplify Admin Navigation

Current admin navigation should be grouped around operator work, not model objects.

Recommended MVP admin nav:

```text
Dashboard
Review
Opportunities
Atlas
Leads
Sources
Settings
```

### Suggested grouping

#### Dashboard

Purpose:

```text
What changed?
What needs attention?
What is ready?
```

#### Review

Purpose:

```text
Clear pending work.
```

Includes:

```text
Funding to review
Idea suggestions
Relationships
Draft hypotheses
System issues
```

#### Opportunities

Purpose:

```text
Funding and fundable opportunities.
```

Includes:

```text
Funding
Funding import
Funding review
Funding public cards
```

#### Atlas

Purpose:

```text
Public discovery objects.
```

Includes:

```text
Ideas
People
Organizations
Places
Public-safe relationships
```

#### Leads

Purpose:

```text
Private collaboration opportunities.
```

Includes:

```text
Collaboration hypotheses
Lead reports
Target watchlist if present
```

#### Sources

Purpose:

```text
Inputs and evidence.
```

Includes:

```text
Sources
ContentItems
RSS/HTML polling
Submitted URLs
Persona snapshots
```

#### Settings

Purpose:

```text
Risk, providers, caps, diagnostics, and advanced controls.
```

---

## 3. Simplify Funding Detail Page

The Funding detail page currently exposes too many equal-weight actions.

Example current actions:

```text
Mark reviewed
Rebuild effort
Fetch source text
Synthesize draft
Regenerate public card
Generate matches
Archive
```

These are useful, but they should not all appear as primary buttons.

### New Funding mental model

Funding review should answer:

```text
Can this funding opportunity become a useful public card and/or lead-generation signal?
```

### Recommended Funding workflow stages

Display a simple status/stage card:

```text
Needs source
Needs draft
Needs review
Ready to publish
Published
Archived
```

Use existing data to infer stage where possible.

### Top-level actions

Show only one primary recommended action, plus at most one or two secondary actions.

Examples:

#### If no source text

```text
Primary: Read from source link
Secondary: Edit manually
```

#### If source text exists but no synthesis draft

```text
Primary: Create review draft
Secondary: Edit manually
```

#### If synthesis draft exists

```text
Primary: Review draft
Secondary: Discard draft
```

#### If reviewed but not public

```text
Primary: Publish card
Secondary: Preview public card
```

#### If public

```text
Primary: Preview public page
Secondary: Review relationships
```

### Advanced Tools panel

Move lower-level operations into a collapsed panel:

```text
Advanced Tools
  Fetch source text / Read from source link
  Synthesize draft / Create review draft
  Regenerate public card / Rewrite public summary
  Rebuild effort
  Generate matches / Find related Ideas and people
  Clear fetch error
  View LLM runs
  Archive
```

Archive can remain visible as a danger action if that matches current admin patterns, but it should not compete visually with the primary review action.

---

## 4. Rename Technical Actions Into Operator Language

Use plain language where possible.

Recommended labels:

```text
Fetch source text        → Read from source link
Synthesize draft         → Create review draft
Regenerate public card   → Rewrite public summary
Rebuild effort           → Recalculate effort
Generate matches         → Find related Ideas and people
Mark reviewed            → Mark ready / Mark reviewed
LLMRun                   → Model run / Generation log
```

Do not rename database fields or internal function names unless needed. This is primarily UI copy.

---

## 5. Add Clear Public/Private/Review Status Badges

Across admin detail/list pages, make status obvious.

At minimum, use badges for:

```text
Private
Public
Public-safe
Needs review
Reviewed
Draft
Archived
LLM generated
Manual override
```

Priority pages:

```text
Funding detail
Funding list
Idea detail/list
Idea suggestions
Matching dashboard
Match detail
Review dashboard
```

The operator should always know:

```text
Will this appear publicly?
Has a human reviewed it?
Was it generated by a model?
Is there a private rationale?
```

---

## 6. Improve Review Dashboard Prominence

The Review page should become the main operator workflow.

Do not add complex new review logic unless it already exists.

This sprint should ensure Review is:

```text
easy to find
clearly labeled
visually prioritized in admin nav
organized by work to clear
```

Recommended Review groups:

```text
Funding needing review
Idea suggestions
Relationships needing review
Draft hypotheses
Failed model/fetch runs
```

Each review item should show:

```text
title
object type
reason for review
public/private status
primary action
```

---

## 7. Preserve Advanced Testing Controls

Do not remove existing controls.

Move dense/testing/debug controls into:

```text
Advanced Tools
Diagnostics
Generation details
```

This keeps the app testable without overwhelming day-to-day operation.

---

# Out of Scope

Do not implement these in this sprint:

```text
new models
new database migrations unless absolutely required for UI state
new LLM prompts
new LLM workflows
new matching logic
new hypothesis generation
LeadReport migration
persistent editable Settings
public graph visualization
public Places pages
batch operations
email/outreach features
major CSS/design-system rewrite
```

This is a UX simplification pass, not a backend capability sprint.

---

# Acceptance Criteria

Sprint 04A is complete when:

```text
Public top-level nav is simplified and no longer exposes every entity type.
Entity pages remain accessible through Explore/Search/related links.
Admin nav is grouped around operator workflows.
Review is more prominent in the admin experience.
Funding detail shows one obvious recommended primary action.
Funding advanced/backend actions are collapsed or visually de-emphasized.
Funding action labels use operator-friendly language.
Public/private/review badges are clearer on core admin pages.
Advanced/debug/LLM controls remain available but are not the default focus.
Existing Funding, Idea, Matching, Review, Settings, and public routes still work.
Public/private safety rules remain unchanged.
Existing tests pass.
```

---

# Required Tests

Add or update tests for:

```text
public nav renders simplified items
removed top-level entity nav links do not break entity routes
admin nav renders new group labels
funding detail renders recommended action based on state
advanced funding actions remain available
public/private/review badges render on key pages
review page remains accessible
public routes still filter private/unreviewed data
```

Run focused tests:

```bash
pytest tests/test_public_routes.py tests/test_public_funding_routes.py tests/test_public_ideas_routes.py
pytest tests/test_admin_funding_routes.py tests/test_admin_ideas_routes.py tests/test_admin_matching_routes.py
pytest tests/test_admin_settings_routes.py
```

If exact test filenames differ, run the closest existing public/admin route tests.

Then run the full suite:

```bash
pytest
```

---

# Manual Testing Path

## Public

1. Open `/`.
2. Confirm nav is simple and experience-oriented.
3. Open `/explore/`.
4. Confirm entity discovery still works.
5. Open `/search`.
6. Confirm search still works.
7. Open direct entity routes:
   - `/people/`
   - `/organizations/`
   - `/ideas/`
   - `/funding/`
8. Confirm routes still work even if not top-level nav items.

## Admin

1. Open `/admin/`.
2. Confirm nav is grouped around workflows.
3. Open `/admin/review`.
4. Confirm review is easy to find and understandable.
5. Open a Funding detail page.
6. Confirm there is one obvious recommended action.
7. Confirm advanced actions are collapsed or visually secondary.
8. Confirm action labels are operator-friendly.
9. Confirm public/private/review status is obvious.
10. Confirm existing advanced actions still work.

---

# Suggested Implementation Order

## Step 1 — Inspect current templates

Find:

```text
public nav template
admin nav template
Funding detail template
Review dashboard template
shared badge/button components if present
admin CSS
public CSS
```

## Step 2 — Simplify public nav

Change only nav and related labels.

Do not delete routes.

## Step 3 — Simplify admin nav

Regroup labels/links.

Do not delete routes.

## Step 4 — Refactor Funding detail actions

Add:

```text
status/stage card
recommended primary action
secondary action
Advanced Tools panel
operator-friendly labels
```

## Step 5 — Add/standardize badges

Use existing CSS if possible.

Avoid large styling rewrites.

## Step 6 — Tests

Update route/template tests.

Run focused then full suite.

---

# Cursor Directive

Use this exact instruction for the coding agent:

```text
Read docs/synapse_mvp_ux_reset_and_roadmap.md for product direction, but only implement docs/sprints/sprint_04a_ux_simplification.md.

This is a UX simplification sprint. Do not add new backend capability.

Focus on simplifying public navigation, admin navigation, Funding detail action hierarchy, review prominence, operator-friendly labels, and public/private/review badges.

Keep all existing advanced controls available, but move them behind Advanced Tools or visually de-emphasize them.

Do not remove routes. Do not break existing tests. Do not implement Collaboration Hypotheses in this sprint.
```

---

# Final Note

This sprint is successful if Synapse feels less like a database and more like a cockpit.

The operator should not need to understand the internal pipeline to know what to do next.
