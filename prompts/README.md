# Synapse prompts (editable copy)

Templates are plain text loaded at qualification time ([`app/leads/prompt_loader.py`](../app/leads/prompt_loader.py)). Do not commit secrets.

The bundled copy below is the default when the DB has no override. **Admin → Leads → Lead pipeline** can edit and save the prompt in-app; that copy overrides the file and bumps the prompt version when the text changes.

## `qualified_lead.txt`

Placeholders (literal substrings):

| Placeholder | Replaced with |
|-------------|----------------|
| `{{hub_context}}` | Serialized Hub content items |
| `{{candidate}}` | Single world `ContentItem` block |
| `{{entity_catalog}}` | Tagged entities union for Hub + candidate source |

When you edit only the repo file, set **`SYNAPSE_LEADS_PROMPT_VERSION`** (or bump the version in **Lead pipeline**) so reruns dedupe cleanly against new prompts. In-app edits bump the stored version automatically.
