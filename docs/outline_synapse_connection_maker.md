# Synapse × Connection Maker — collaboration outline

**Purpose:** Align two Neurotech Hub–adjacent efforts: keep **[Synapse](..)** as the primary system-of-record repo, treat **[Connection Maker](https://github.com/Neurotech-Hub/Connection-maker)** (CM) as an exploratory playground today, and define how to **merge the best of both** over time — especially **entity-centric identity** enriched by agentic workflows, without giving up Synapse’s **relational ingestion model**.

This document is an **outline for discussion**, not an approved roadmap.

---

## 1. How we’re positioning the repos

| | **Synapse** | **Connection Maker** |
|---|-------------|----------------------|
| **Role now** | Main app: ingest, dedupe, admin ops, Hub-vs-world **lead qualification**, exports | FastAPI + Next experiment: PI registry, personas, ingest toward **digital twin** UX |
| **UX bias** | Admin tables, filters, CSV — accurate for ops, feels “spreadsheet-like” | Card grid + PI detail pages — scan-friendly summaries, badges, inferred blocks |
| **Truth for merge** | **Canonical data + relationships live here first** | Patterns, prompts, UX, and spikes inform what we bolt onto Synapse |

---

## 2. What CM’s UI is teaching us (screenshots)

From the CM UI (localhost examples in the playground):

- **PI registry**: grid of cards with **name**, **affiliation**, **short research blurb**, **topic tags**, a **papers / 90d** (or similar) activity signal, **last updated**.
- **PI detail**: richer **bio/summary**, **keyword tags**, **research focus** lists, **methods** tags, **funding signals** (e.g. NIH R01, NSF), **inferred current projects** (explicitly labeled as synthesized, not manually curated).
- **Publications**: linked titles, dates, PMID-style identifiers — grounding the persona in provenance similar in spirit to our `content_item` + links.
- **Nav affordances**: “All PIs,” search/filter (“All scores”), and placeholders for **Matches** and **Newsletters** — roadmap surfacing.

**Takeaway:** CM optimizes **at-a-glance identity** and **narrative trust** (“inferred”, tags, scoring). Synapse optimizes **provenance and pipes** (`source` → `content_item` → optional `lead_candidate`, entity tagging on sources).

---

## 3. Synapse entities today vs CM-style “identity”

### Current Synapse (`entity`)

- **`slug`**, **`kind`** (`lab` \| `person` \| `place` \| `org`), **`display_name`**, **`notes`**, timestamps.
- **Many-to-many** with **`source`** via `source_entity` (tracked entities on each source UI).
- **Leads**: optional `LeadCandidate.entity_id`; qualification uses an **entity catalog** derived from Hub + candidate sources.

**Strength:** Clear relational spine — entities are join keys across ingestion and lead output.

**Gap vs CM:** No first-class store for **synthesized profile fields** (focus bullets, funding tags, “inferred projects,” scores), weak **surface area in the UI** for “who is this entity as a researcher?” compared to CM’s PI page.

---

## 4. Why Synapse still looks “more expandable”

- **Source diversity:** RSS + HTML monitors + public URL submission + snapshots — not limited to PubMed-centric PI feeds.
- **Operational closure:** Poll logs, qualification logs, bulk actions, CSV export — built for recurring operator use.
- **Extensibility hook:** Any new **derived artifact** can hang off existing rows:  
  `Source` / `ContentItem` / `Entity` / `LeadCandidate` (+ future materialized views or JSON blobs with versions).

CM’s compelling piece is less the transport and more **where agentic summaries land in the UX**.

---

## 5. Structured vs unstructured — the decision lens

Ask for each field or feature:

| Question | Prefer **structured** (columns / FKs / enums) when… | Prefer **unstructured / derived** (text, JSON blob, embeddings sidecar) when… |
|---------|-----------------------------------------------------|----------------------------------------------------------------------------------|
| Joins & reporting | You filter, sort, export, or constrain (e.g. “all leads for entity X”) | You rarely slice on it verbatim |
| Provenance | You need audit trail to **specific items** (`content_item`, PMID, grant ID) | It’s genuinely narrative synthesis |
| Versioning | Business rules dedupe or invalidate old rows (**prompt_version** pattern) | You can re-render from prompts + frozen inputs |
| Human editability | Operators correct row-level facts | Editors tweak prompts/caps rather than prose cells |

**Working hypothesis:**

- Keep **identifiers and edges** structured: `entity_id`, `source_id`, `content_item_id`, slug, PubMed/link URLs, timestamps.
- Add **structured “facets”** only when CM proves they repeat (funding tier, NIH vs NSF bucket) *and* you need dashboards.
- Park **fluid identity prose** (“inferred projects”, expanded bios) as **versioned blobs** keyed by entity + `(prompt_version | snapshot_id)` until we know query needs.

---

## 6. Merging directions (incremental — no big-bang repo merge)

### A. UX / surface

- Optional **Synapse entity profile** route (even read-only): card-like summary fed from structured fields + derived blocks (parity with CM’s PI detail *without* abandoning tables for admin-heavy pages).
- Reuse CM patterns: **badges**, **inferred** labeling, **last updated**, **papers N / window** computed from linked sources’ items.

### B. Data model (sketches for debate)

- `entity_identity_snapshot` (or JSON column on `entity` with versioning) holding: summary, topics[], methods[], funding_tags[], inferred_projects[], `generated_at`, `source_window` metadata.
- Separate **facet tables** later if facets become filters (e.g. `entity_funding_signal`).

### C. Intelligence

- Align with Synapse’s existing pattern: **Ollama-backed jobs** writing structured outputs (like lead qualification) with **explicit prompt versioning** (already mirrored for the qualified-lead prompt in admin).
- Optional **dual-model** spike (cloud for long-form prose) mirrors CM’s split — decide per cost/privacy/env.

### D. Integration mechanics (if CM stays separate briefly)

- **Read-only export** from Synapse (entities + recent `content_item` abstracts) → CM ingest, or vice versa webhook on `content_item` insert — only if duplication pain justifies glue.

Prefer **fewer databases of truth**: pull CM learnings **into Synapse migrations** rather than indefinitely syncing two Postgreses.

---

## 7. Open questions for collaborators

1. **Entity–source model:** Is tagging enough, or do we need **primary PI** vs **contributor** roles on `source_entity` for scoring (e.g. “papers / 90d” only from “primary” feeds)?
2. **Identity refresh:** On-demand (“Refresh identity” button), **scheduled**, or triggered when **new items** attach to tagged sources?
3. **Collaboration scores / matches:** Pure derived UI, or new tables keyed by `(entity_a, entity_b, version)`?
4. **Privacy / consent:** Summaries inferred from publications may still need Hub policy gates before any public route.

---

## 8. Next steps (when the group picks this up)

1. Freeze this outline in a PR and comment with **prioritized wedges** (e.g. entity profile MVP vs ingest unchanged).
2. Spike **one** derived block (e.g. “topic tags” from recent items for `kind=person`) using existing `content_item` text + one prompt — store as versioned blob on `entity`.
3. Borrow CM’s **wording norms** (“Inferred”) in Synapse UI anywhere we show model-generated prose.

---

*Last updated: outline draft for internal collaboration.*
