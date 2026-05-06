# Public Site UX

The public site is now intentionally small. It should make it easy to submit a public web location, show recently ingested public-safe content, and provide light browsing/search over public entities and opportunities.

## Homepage

Hero copy:

```text
Tell us what to watch.
```

Subtitle:

```text
Ready to ingest and draw connections from any web location.
```

After the submit form, the homepage should show only:

- `The Latest`

Do not add homepage sections for spotlights, themes, relationship graphs, or broad product positioning until the ingestion and lead-candidate loop is stable.

## Navigation

Primary navigation:

- Home
- Explore
- Opportunities
- expandable search control

Search should be a subtle round icon at the end of the nav. On click/focus it expands into a search input; on blur or escape it collapses when empty.

Do not add an About tab. The footer should keep `Team sign-in` and use `Say Hello` with `mailto:gaidica@wustl.edu`.

## Language

Avoid product language that implies a polished graph or broad discovery product before the MVP earns it. In active public templates, avoid:

- `Atlas`
- public Idea pages
- relationship claims
- private lead language
- internal scoring language

## Public Content

Public pages may show:

- recent public-safe content items;
- people, organizations, and places that have approved public sources;
- simple funding/opportunity pages when reviewed and public;
- source links and public-safe summaries.

Public pages must not show:

- private lead candidates;
- private notes;
- LLM failures or confidence internals;
- admin review status;
- compatibility-only storage concepts.

## Current MVP Boundary

Ideas are removed from the active public product. If concept extraction returns later, it should feed the Lead Candidate backend first, not reintroduce a manual public Ideas scaffold.
