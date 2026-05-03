# Synapse prompts (editable copy)

Hub lead reports load plain-text templates named `lead_report_*.txt` ([`app/leads/report_pipeline.py`](../app/leads/report_pipeline.py)). Do not commit secrets.

Adjust evidence caps in [`app/leads/lead_report_budgets.py`](../app/leads/lead_report_budgets.py), or override with optional `SYNAPSE_LEAD_REPORT_*` env vars. Ollama long-context size is tuned via `SYNAPSE_LEAD_REPORT_NUM_CTX`.
