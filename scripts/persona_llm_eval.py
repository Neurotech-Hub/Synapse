#!/usr/bin/env python3
"""Persona LLM evaluation harness / rollout checklist (no API calls by default).

Usage:
  python scripts/persona_llm_eval.py

Prints environment expectations and rubric items for A/B persona quality review.
Set OPENAI_API_KEY and run admin persona rebuilds manually; compare outputs against this rubric.
"""

from __future__ import annotations

import os

RUBRIC = """
Rubric (manual scoring 1–5 each):
- Specificity: avoids generic lab-boilerplate when titles/snippets warrant detail.
- Evidence coverage: reflects major themes visible in owned-source items.
- Recency: incremental/light modes emphasize recent RSS weighting without erasing stable identity.
- Stability: incremental update does not erase accurate prior fields without contradicting evidence.
- Cost sanity: note token/latency from logs for full vs incremental rebuild_modes.
"""


def main() -> None:
    has_openai = bool((os.environ.get("OPENAI_API_KEY") or "").strip())
    ident = (os.environ.get("SYNAPSE_LLM_IDENTITY_PROVIDER") or "(auto)").strip()
    poll_mode = (os.environ.get("SYNAPSE_POLL_PERSONA_REBUILD_MODE") or "incremental").strip()
    dash_mode = (os.environ.get("SYNAPSE_DASH_IDENTITY_REBUILD_MODE") or "incremental").strip()

    print("Synapse persona LLM rollout checklist\n")
    print(f"  OPENAI_API_KEY set: {has_openai}")
    print(f"  SYNAPSE_LLM_IDENTITY_PROVIDER: {ident}")
    print(f"  SYNAPSE_POLL_PERSONA_REBUILD_MODE: {poll_mode}")
    print(f"  SYNAPSE_DASH_IDENTITY_REBUILD_MODE: {dash_mode}")
    print(RUBRIC)
    print(
        "Rollout gate suggestion: require incremental persona delta quality ≥ baseline full rebuild "
        "on a fixed fixture set before defaulting poll burst to incremental-only schedules."
    )


if __name__ == "__main__":
    main()
