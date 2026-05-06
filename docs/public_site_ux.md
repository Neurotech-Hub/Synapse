# Public Site UX Spec

## Purpose

This document defines the public-facing experience for Synapse as it evolves from a directory-like research-intelligence site into an exploratory **research opportunity atlas** for the Neurotech Hub.

The public site should make Synapse feel useful even before a visitor understands the internal lead-generation system. It should help researchers, staff, collaborators, funders, and curious visitors explore people, organizations, places, ideas, funding opportunities, and recent activity.

The private/admin system can use the same underlying graph to generate collaboration hypotheses, lead reports, and funding-aligned outreach. The public system should expose only the generous, useful, and non-sensitive parts of that graph.

---

## Product framing

### Short framing

> Synapse public site is a living map of neurotechnology opportunities.

### Longer framing

Synapse helps visitors explore the people, places, organizations, ideas, tools, and funding opportunities shaping neuroscience technology. It turns a scattered corpus of public research activity into approachable discovery pages and lightweight pathways for collaboration.

### Design intent

The public site should feel:

- **Exploratory** — visitors can wander from a person to an idea to a building to a funding opportunity.
- **Resourceful** — pages should help users learn, not just promote the Hub.
- **Evidence-aware** — claims should be grounded in public content items or curated summaries.
- **Fun** — maps, idea constellations, funding radar, and related-entity cards should make the site feel alive.
- **Generous** — public pages should give away useful context without exposing private lead logic.
- **Low-friction** — every page should have an obvious next step: explore, submit a link, request support, or open the source.

---

## Relationship to existing Synapse surfaces

Synapse already has two major surfaces:

1. **Public site**
   - landing page
   - URL submit
   - people and organization listings/detail pages
   - Latest content cards

2. **Admin workspace**
   - source approval
   - content curation
   - persona snapshots
   - organizations, people, buildings, regions
   - lead reports
   - Hub settings

This spec expands the public surface while preserving the admin/private boundary.

---

## Public/private boundary

### Public should show

- Published people, organizations, places, ideas, and funding opportunities.
- Public summaries derived from approved sources.
- Tags, methods, research themes, and general relationships.
- Source links and source snippets when appropriate.
- Funding cards with effort index, amount text, deadline text, and external links.
- Related entities such as people connected to an idea or ideas related to a funding opportunity.
- Calls to action for requesting support or submitting sources.

### Public should not show

- Internal lead scores.
- Private collaboration hypotheses.
- Inferred pain points about specific researchers.
- Outreach recommendations.
- Relationship strategy.
- Admin-only notes.
- Private confidence flags or model failure details.
- Anything derived from unpublished or restricted content.

### Private/admin should show

- Match scores and score components.
- Lead/collaboration hypothesis rationale.
- Internal Hub fit analysis.
- Funding fit analysis.
- Recommended action.
- Reviewed/dismissed/contacted status.
- Private notes.
- Model confidence and synthesis failures.

---

## Core public entities

The public site should organize around six primary entity types.

```text
People
Organizations
Places
Ideas
Funding
Latest
```

### People

A person page describes what someone appears to work on, based on public evidence and curated persona data.

Public page should include:

- name
- title/role if known
- organization affiliations
- short public summary
- research themes
- methods and tools
- related ideas
- related organizations
- related places
- recent public content
- external links
- submit correction / suggest source action

Avoid:

- private Hub fit score
- outreach strategy
- inferred unmet needs unless converted into a generic public phrasing

### Organizations

An organization page describes a lab, center, department, company, nonprofit, or program.

Public page should include:

- name
- short public summary
- affiliated people
- related places/buildings
- research themes
- related ideas
- recent public content
- external links
- possibly related funding opportunities

Avoid:

- internal account-priority scoring
- private business-development notes

### Places

A place page describes where research activity happens.

Place may mean:

- building
- campus region
- floor/zone if modeled later
- city/region if Synapse expands beyond campus

Public page should include:

- name
- map/location representation where available
- organizations associated with the place
- people associated with the place
- ideas/research themes concentrated there
- recent public activity
- external links

Place pages are especially important for making the site feel like an atlas rather than a database.

### Ideas

An idea page describes a research theme, technical concept, experimental direction, or buildable opportunity.

Public page should include:

- idea title
- short explanation
- why it matters
- related people
- related organizations
- related places
- related funding
- Hub capabilities that may support the idea
- recent public content
- suggested next step

Ideas are the main connective tissue between people, organizations, places, funding, and Hub capabilities.

### Funding

A funding page/card describes a funding opportunity without becoming a grant-management system.

Public card should include:

- title
- sponsor
- deadline text/date if known
- amount text if known
- effort index
- topic/method tags
- public summary
- external link
- related ideas

Public page may include:

- eligibility summary
- who should care
- possible Hub relevance, phrased broadly
- missing information notice if extraction confidence is low

Avoid:

- complex grant instructions
- internal prioritization
- private recommended targets

### Latest

Latest should remain a curated public activity feed but become more connected.

Cards should include:

- title
- source
- date
- public snippet
- linked people/orgs/ideas/funding when available
- reason it is interesting, if curated

---

## Information architecture

### Primary navigation

```text
Home
Explore
Ideas
Funding
Latest
Submit a Link
Request Support
```

### Explore dropdown

```text
People
Organizations
Places
Ideas
Funding
Latest
```

### Admin-only navigation remains separate

Admin navigation should not leak into the public layout except through a small login link if desired.

---

## Proposed public routes

```text
/
/explore
/people
/people/<slug>
/organizations
/organizations/<slug>
/places
/places/<slug>
/ideas
/ideas/<slug>
/funding
/funding/<slug>
/latest
/submit
/request-support
/search
```

Optional later routes:

```text
/atlas
/radar
/buildable-ideas
/map
/topics/<slug>
/methods/<slug>
```

---

## Homepage UX

### Goal

The homepage should immediately communicate that this is not a static directory. It is an exploratory research atlas.

### Hero copy options

Option A:

```text
Explore the people, places, ideas, tools, and funding shaping neuroscience technology.
```

Option B:

```text
A living map of neurotechnology opportunity.
```

Option C:

```text
Find collaborators, ideas, funding, and technical paths across the neuroscience ecosystem.
```

### Hero actions

Primary:

```text
Explore the Atlas
```

Secondary:

```text
Submit a Link
```

Tertiary:

```text
Request Hub Support
```

### Homepage sections

1. **Search / explore bar**
   - Search people, organizations, ideas, places, funding.

2. **Idea spotlight**
   - 3-6 public idea cards.

3. **Funding radar**
   - Active funding cards with effort index and deadline.

4. **Latest signals**
   - Curated public content.

5. **Map / places teaser**
   - Buildings, regions, or research clusters.

6. **How the Hub helps**
   - Short capability cards.

7. **Submit something useful**
   - URL submission CTA.

---

## Explore page

### Goal

Provide a single entry point into the whole graph.

### Layout

```text
Search bar
Entity type filters
Topic/method filters
Featured clusters
Recently updated entities
```

### Entity cards

Each card should show:

- entity type badge
- name/title
- one-sentence summary
- tags
- related count indicators
- updated date if useful

Example card:

```text
Idea
Automated Home-Cage Behavior
Long-duration behavioral systems that combine sensing, reward delivery, and continuous monitoring.
Tags: behavior, embedded systems, reward delivery
Related: 8 people · 3 organizations · 2 funding opportunities
```

---

## People listing UX

### Filters

- organization
- place/building
- idea
- method
- recent activity

### Sort options

- recently updated
- name
- most connected
- newest

### Card fields

```text
Name
Affiliation
Short summary
Tags/methods
Related ideas
Recent activity indicator
```

### Page-level CTA

```text
Know a missing source for this person? Submit a link.
```

---

## Person detail UX

### Header

```text
Name
Role / affiliation
Public summary
External links
```

### Sections

1. **What they work on**
   - public persona summary
   - focus areas
   - methods

2. **Connected ideas**
   - cards for related ideas

3. **Recent public signals**
   - content items

4. **Organizations and places**
   - affiliation cards
   - building/location if available

5. **Related funding**
   - only if public-safe and high-confidence

6. **Sources**
   - optional compact list

7. **Suggest an update**
   - submit URL

### Important language guideline

Use public-friendly language:

```text
Related to this work
```

Do not use private/business-development language:

```text
Lead fit
Sales opportunity
Pain point
Target
```

---

## Organization listing UX

### Filters

- organization type
- place/building
- idea
- method
- recent activity

### Card fields

```text
Organization name
Type
Short summary
Related people count
Related ideas
Recent activity
```

---

## Organization detail UX

### Sections

1. **Overview**
2. **People**
3. **Research themes / ideas**
4. **Places**
5. **Recent public content**
6. **Funding connections**
7. **External links**

### Optional visualization

A small network/constellation component:

```text
Organization at center
People around it
Ideas around people
Funding opportunities as outer ring
```

This can be static in v1 and interactive later.

---

## Places UX

### Places listing

This can be map-first or card-first.

MVP:

- card grid
- optional region filters

Later:

- interactive map
- campus/building overlays
- research density markers

### Place card fields

```text
Place name
Type: building / region / campus / city
Associated organizations
Associated ideas
Short summary
```

### Place detail sections

1. **Overview**
2. **Organizations here**
3. **People here**
4. **Ideas/research themes here**
5. **Recent activity**
6. **Map or location context**

### UX principle

Place pages should answer:

> What happens here?

Not just:

> What is this building?

---

## Ideas UX

### Ideas listing

Ideas should be one of the most visually interesting sections.

Filters:

- method
- organism/species if available
- modality
- hardware/software/data
- Hub capability
- funding availability
- recent activity

Sort:

- featured
- recently updated
- most connected
- funding available

### Idea card fields

```text
Idea title
Short description
Tags
Related people/orgs/funding counts
Hub capability badge if relevant
```

### Idea detail page

Sections:

1. **Idea overview**
   - what this is
   - why it matters

2. **How the Hub could help**
   - public capability framing, not private lead logic

3. **People connected to this idea**

4. **Organizations connected to this idea**

5. **Places connected to this idea**

6. **Funding that may support this idea**

7. **Recent public signals**

8. **Related ideas**

### Public copy examples

```text
This idea connects long-duration behavioral monitoring, embedded sensing, and automated reward delivery.
```

```text
The Neurotech Hub may support work in this area through rapid prototyping, embedded systems, instrumentation, and experimental integration.
```

Avoid:

```text
This is a high-priority lead.
```

---

## Funding UX

### Funding listing

The funding page should feel like a lightweight radar, not a grant database.

Suggested page title:

```text
Funding Radar
```

Suggested subtitle:

```text
A curated view of opportunities that may support neuroscience technology, methods, tools, and collaborative research.
```

### Filters

- status: active/upcoming/expired/archive
- effort: mild/moderate/heavy/unknown
- sponsor type
- deadline window
- topic tag
- method tag
- related idea
- amount known/unknown

### Sort

- deadline soon
- recently added
- effort low to high
- amount high to low, when parseable
- most related ideas

### Funding card fields

```text
Title
Sponsor
Deadline
Amount text
Effort index
Tags
One-sentence summary
External link
```

### Effort index display

Use simple labels:

```text
Effort: Mild
Effort: Moderate
Effort: Heavy
Effort: Unknown
```

Optional tooltip:

```text
Effort reflects likely application burden, not scientific value.
```

### Funding detail page

Sections:

1. **Summary**
2. **Key details**
   - sponsor
   - deadline
   - amount
   - effort
   - external link
3. **Who should care**
4. **Relevant ideas**
5. **Possible Hub relevance**
6. **Source and caveats**

### Important funding UX rule

Always refer users to the official source for details.

Suggested language:

```text
This summary is intended for discovery. Review the official funding page before making decisions.
```

---

## Latest UX

### Goal

Latest should become the “signal stream” of Synapse.

### Card fields

```text
Title
Date
Source
Snippet
Related entities
Why this matters, if curated
```

### Related entity chips

Example:

```text
Person: Jane Doe
Idea: Closed-loop behavior
Funding: Tool development grants
Organization: Example Lab
```

### Curation logic

Latest should avoid becoming a raw ingest dump. Prefer:

- curated items
- high-signal recent items
- items tied to public ideas
- items with updated personas
- items linked to funding or collaboration themes

---

## Submit URL UX

### Current role

Synapse already supports public URL submission that creates pending sources for admin review.

### Expanded role

The submission flow should invite visitors to contribute to the atlas.

### Form fields

MVP:

```text
URL
Optional note
Submitter email optional
```

Later:

```text
What is this about?
  person
  organization
  place
  idea
  funding
  other
```

### After-submit message

```text
Thanks — this link will be reviewed before appearing in Synapse.
```

### Anti-spam / quality

- rate limit
- canonicalize URL
- detect duplicate submissions
- keep admin review required
- do not auto-publish public submissions

---

## Request support UX

### Purpose

This page is a public intake path for researchers who want Hub help.

### Positioning

It should not feel like a generic contact form. It should feel like a project-shaping form.

### Suggested fields

```text
Name
Email
Organization/lab
Project area
What are you trying to build or measure?
Where are you stuck?
Timeline
Funding status
Relevant links
```

### Optional lightweight classification

After submission, Synapse can privately classify the request into:

```text
embedded systems
behavioral hardware
software/data pipeline
mechanical fabrication
instrumentation
cloud/data sync
consultation
other
```

This classification should be admin/private by default.

---

## Search UX

### MVP search

Use existing SQL/substr search over public entities and content.

Search should return grouped results:

```text
People
Organizations
Places
Ideas
Funding
Latest
```

### Later search

Potential future additions:

- embeddings
- semantic search
- query suggestions
- tag autocomplete
- “related to this” search

### Search result card

```text
Entity type
Title/name
Short snippet
Matched tags
Related entities
```

---

## Cross-linking patterns

The core UX pattern is that every page should lead somewhere else.

### Entity chip

```text
[Idea] Closed-loop behavior
[Person] Jane Doe
[Funding] Foundation pilot award
[Place] Neuroscience Research Building
```

### Related cards

Use related cards for high-value links:

```text
Related funding
Related people
Related organizations
Related ideas
```

### Evidence snippets

When useful, show a short source-backed snippet:

```text
Based on recent public content from Example Source.
```

Do not overburden the public UX with citations unless the page needs scientific/source trust. The external source link is usually enough for v1.

---

## Visual language

### Overall style

- clean scientific aesthetic
- warm and exploratory
- cards with lightweight badges
- subtle network/map motifs
- not too corporate
- not too dense

### Motifs

Potential recurring motifs:

```text
Atlas
Radar
Constellation
Signal
Pathway
Opportunity
```

### Suggested labels

```text
Funding Radar
Idea Constellations
Research Atlas
Latest Signals
Buildable Ideas
```

### Badge types

```text
Person
Organization
Place
Idea
Funding
Latest
Method
Tool
Hub Capability
Effort
```

---

## Public page states

### Empty state

Example:

```text
No related funding is published yet.
```

Avoid:

```text
No leads found.
```

### Low-confidence state

Example:

```text
Some details are incomplete. Please review the official source.
```

### Draft/unpublished state

Draft entities should not appear publicly.

### Expired funding state

Expired funding can remain public if useful, but should be clearly labeled:

```text
Expired
```

and excluded from default active funding radar views.

---

## Public-safe relationship language

Use:

```text
Related to
Connected ideas
Relevant funding
Public signals
May support
Could be useful for
```

Avoid:

```text
Lead
Target
Pain point
Outreach strategy
High priority prospect
Sales fit
```

---

## Data requirements by page

### Home

Requires:

- featured ideas
- active funding cards
- latest curated content
- public counts
- public settings/copy

### People

Requires:

- public people
- current persona snapshot
- public relationship edges
- recent public content

### Organizations

Requires:

- public organizations
- public member relationships
- public place relationships
- public idea relationships

### Places

Requires:

- public places/buildings/regions
- organization links
- optional location/geometry

### Ideas

Requires:

- public ideas
- public match edges
- public related content
- related funding

### Funding

Requires:

- public funding opportunities
- status/deadline fields
- effort index
- tags
- related ideas

### Latest

Requires:

- curated public feed items
- public related entity links

---

## Feature flags

Consider feature flags or config gates for unfinished surfaces.

```text
SYNAPSE_PUBLIC_IDEAS_ENABLED
SYNAPSE_PUBLIC_FUNDING_ENABLED
SYNAPSE_PUBLIC_PLACES_ENABLED
SYNAPSE_PUBLIC_ATLAS_ENABLED
SYNAPSE_PUBLIC_SEARCH_ENABLED
SYNAPSE_PUBLIC_REQUEST_SUPPORT_ENABLED
```

This allows incremental release without hiding all work behind branches.

---

## Template architecture

### Suggested route organization

Current public routes are in:

```text
app/web/public_routes.py
```

As public UX grows, consider splitting public routes into modules:

```text
app/web/public/
  __init__.py
  routes.py
  people.py
  organizations.py
  places.py
  ideas.py
  funding.py
  latest.py
  search.py
  intake.py
```

This is not required for MVP, but it will help avoid a single large public route file.

### Suggested template organization

```text
app/templates/public/
  base.html
  home.html
  explore.html
  people/
    index.html
    detail.html
    _card.html
  organizations/
    index.html
    detail.html
    _card.html
  places/
    index.html
    detail.html
    _card.html
  ideas/
    index.html
    detail.html
    _card.html
  funding/
    index.html
    detail.html
    _card.html
  latest/
    index.html
    _card.html
  components/
    _entity_chip.html
    _related_cards.html
    _tag_filters.html
    _search_box.html
    _empty_state.html
    _source_link.html
```

### Component principle

Invest early in reusable cards and chips. The same entity relationships appear everywhere.

---

## Matching visibility rules

Not every match should be public.

### Public-safe match edge

A match edge can be public when:

- both entities are public
- the relationship is general and non-sensitive
- rationale does not include private notes
- confidence is above a configurable threshold
- admin has not hidden it

### Private-only match edge

Keep private when:

- it expresses outreach strategy
- it mentions unmet needs or pain points
- it involves private Hub evaluation
- it involves low confidence
- it comes from a private content source

### Suggested fields

```text
MatchEdge.public_visible
MatchEdge.public_label
MatchEdge.public_rationale
MatchEdge.private_rationale
```

---

## SEO and shareability

Public pages should have good metadata because pages may be shared with collaborators.

### Each public entity page should include

```text
<title>
meta description
canonical URL
Open Graph title
Open Graph description
Open Graph image, later
```

### Slugs

Use stable slugs:

```text
/ideas/automated-home-cage-behavior
/funding/example-foundation-pilot-award-2026
/people/jane-doe
```

If names change, preserve redirects if possible.

---

## Accessibility

Baseline requirements:

- keyboard navigable cards and filters
- semantic headings
- visible focus states
- alt text for maps/visualizations
- no color-only meaning for effort/status badges
- sufficient contrast
- mobile-friendly card stacking

---

## Performance

Public pages should remain fast.

### MVP

- server-rendered pages
- paginated listings
- limited related cards per section
- precomputed snapshots and match edges

### Avoid

- generating LLM text during public request/response cycle
- expensive graph traversal on every page load
- loading all entity relationships for listing pages

### Later

- cache public page fragments
- materialized public search index
- CDN/static asset optimization
- background match regeneration

---

## Analytics and feedback

Useful public metrics:

```text
page views by entity type
funding card clicks
external source clicks
submit URL conversions
request support conversions
search queries
zero-result searches
popular ideas
popular funding filters
```

Do not overcomplicate initially. Basic server logs or lightweight analytics are enough.

---

## Admin controls needed for public UX

Public UX depends on admin curation.

Admin should be able to:

- publish/unpublish people, orgs, places, ideas, funding
- feature/unfeature ideas
- feature/unfeature funding
- mark funding active/expired/archive
- override summaries
- hide specific relationships
- override public labels
- review submitted links
- preview public pages before publishing

---

## Phased implementation

## Phase A — Public funding and ideas MVP

### Goal

Expose basic public pages for ideas and funding.

### Includes

- `/ideas`
- `/ideas/<slug>`
- `/funding`
- `/funding/<slug>`
- cards and tags
- effort index badge
- external funding link
- basic related ideas/funding links if available

### Excludes

- interactive map
- semantic search
- complex graph visualization
- public match explanations

### Acceptance criteria

- Published ideas appear on `/ideas`.
- Published funding appears on `/funding`.
- Funding cards show title, sponsor, deadline, amount text, effort, tags, and external link.
- Idea detail pages show related funding when relationship edges exist and are public-visible.
- Draft/private entities do not appear publicly.

---

## Phase B — Explore page and cross-linking

### Goal

Create the first unified atlas experience.

### Includes

- `/explore`
- grouped entity search/listing
- reusable entity cards
- reusable entity chips
- related cards across people/orgs/places/ideas/funding

### Acceptance criteria

- Visitor can start at `/explore` and navigate between at least three entity types.
- Related entity chips appear consistently.
- Empty states are public-friendly.

---

## Phase C — Homepage refresh

### Goal

Turn the homepage into a discovery-oriented landing page.

### Includes

- new hero framing
- search/explore CTA
- idea spotlight
- funding radar section
- latest signals
- request support CTA
- submit link CTA

### Acceptance criteria

- Homepage communicates the research atlas concept.
- It exposes ideas, funding, latest, and intake paths.
- It does not expose private lead logic.

---

## Phase D — Places/atlas experience

### Goal

Make places useful and fun.

### Includes

- places listing refresh
- place detail pages with related orgs/people/ideas
- optional static map/region view
- later interactive map

### Acceptance criteria

- Place pages answer “what happens here?”
- Buildings/regions link to public organizations and ideas.

---

## Phase E — Search and filters

### Goal

Make the public site easier to navigate as the corpus grows.

### Includes

- `/search`
- type filters
- tag filters
- funding status/effort filters
- query highlighting if simple

### Acceptance criteria

- Search results are grouped by entity type.
- Zero-result searches provide useful next steps.
- Funding can be filtered by effort and deadline/status.

---

## Phase F — Public graph polish

### Goal

Add exploratory delight after the basics work.

### Includes

- idea constellations
- funding radar visual treatment
- map/atlas interactions
- relationship visualizations
- public topic pages
- shareable cards

### Acceptance criteria

- Visualizations are supplemental, not required for comprehension.
- Pages remain accessible and fast.

---

## Public copy bank

### Site-level copy

```text
A living map of neurotechnology opportunity.
```

```text
Explore the people, places, ideas, tools, and funding shaping neuroscience technology.
```

```text
Follow public research signals across people, organizations, places, ideas, and funding opportunities.
```

### Funding copy

```text
Funding Radar
```

```text
A curated view of opportunities that may support neuroscience technology, methods, tools, and collaborative research.
```

```text
Effort reflects likely application burden, not scientific value.
```

```text
Review the official source before making funding decisions.
```

### Ideas copy

```text
Buildable Ideas
```

```text
Explore research directions where technical infrastructure, collaboration, and funding may come together.
```

### Submit copy

```text
Help improve the atlas. Submit a public link for review.
```

### Request support copy

```text
Have a project that needs technical support? Tell us what you are trying to build, measure, or automate.
```

---

## Non-goals

This public UX should not become:

- a full grant management platform
- a private CRM
- a social network
- a claims-heavy ranking system
- a replacement for official funding pages
- a live LLM chatbot surface in the MVP
- a publication database clone

---

## Agent work packages

## Agent A — Public routes and templates

Owns:

- route scaffolding
- template organization
- listing/detail pages
- pagination
- public/draft visibility filters

Deliverables:

- `/ideas`
- `/funding`
- shared card components
- public base layout updates

## Agent B — Public cards and relationship components

Owns:

- entity cards
- entity chips
- related-card sections
- status/effort badges
- empty states

Deliverables:

- reusable components for all public pages
- consistent public-safe language

## Agent C — Homepage and explore UX

Owns:

- homepage refresh
- `/explore`
- search/explore entry points
- CTA hierarchy

Deliverables:

- discovery-first homepage
- explore page with grouped entities

## Agent D — Funding public UX

Owns:

- funding listing filters
- funding detail page
- effort index display
- external source warnings

Deliverables:

- Funding Radar MVP
- funding detail template

## Agent E — Ideas public UX

Owns:

- idea listing filters
- idea detail page
- related people/orgs/places/funding sections
- Hub capability language

Deliverables:

- idea index/detail pages
- buildable idea presentation pattern

## Agent F — Places/atlas UX

Owns:

- place listing/detail refresh
- map placeholder or static map
- organization/place/idea cross-links

Deliverables:

- place pages that explain research activity
- atlas-ready layout

## Agent G — UX QA and content safety

Owns:

- public/private boundary checks
- accessibility review
- mobile layout review
- language review
- SEO metadata checks

Deliverables:

- public UX QA checklist
- regression tests for unpublished/private content

---

## Test checklist

### Visibility tests

- Draft funding does not appear publicly.
- Draft ideas do not appear publicly.
- Private match edges do not appear publicly.
- Public match edges appear only when both entities are public.

### Routing tests

- Public listing pages load.
- Public detail pages load by slug.
- Unknown slugs return 404.
- Expired funding is labeled correctly.

### Card tests

- Funding card shows effort index.
- Funding card links to official source.
- Idea card shows tags and related counts.
- Entity chips link to the correct public pages.

### UX tests

- Empty states do not mention leads.
- Public pages do not show private rationale.
- Request support page submits successfully.
- Submit link page still creates pending source rows.

### Accessibility tests

- Cards are keyboard navigable.
- Filters are labeled.
- Badge meaning is not color-only.
- Mobile layout stacks correctly.

---

## Open questions

1. Should public people/org pages be opt-in published, or public by default after persona generation?
2. Should funding opportunities remain visible after expiration as an archive?
3. Should public pages show source snippets, or only external links?
4. Should request-support submissions become private `CollaborationHypothesis` seeds?
5. Should idea pages be curated manually first, LLM-generated first, or hybrid?
6. Should the homepage use “Atlas,” “Radar,” “Signals,” or more conventional labels?
7. Should public search include raw content items or only entity pages?

---

## Recommended next implementation sequence

```text
1. Add public visibility flags to Idea and Funding models.
2. Build public card components.
3. Build /ideas and /funding listing/detail routes.
4. Add related entity chips for Idea ↔ Funding.
5. Refresh homepage with idea and funding sections.
6. Add /explore.
7. Expand people/org/place detail pages with related ideas/funding.
8. Add search and filters.
9. Add map/atlas polish.
```

The most important early win is not a perfect visualization. It is giving the public site a new center of gravity around **Ideas** and **Funding Radar**, then letting people, organizations, places, and latest content orbit around those concepts.
