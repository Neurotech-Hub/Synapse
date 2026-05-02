# Synapse

AI-assisted ingestion and lead workflow for Neurotech Hub (see [synapse_scope.md](synapse_scope.md)).

## Run the web app

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
export ADMIN_PASSWORD='choose-a-local-password'   # or ADMIN_PASSWORD_HASH from werkzeug
flask --app wsgi db upgrade   # first time / after model changes
flask --app wsgi run --debug
```

- **Public site:** [http://127.0.0.1:5000/](http://127.0.0.1:5000/) — submit a URL for ingestion (canonicalized; duplicates are detected).
- **Admin:** [http://127.0.0.1:5000/admin/login](http://127.0.0.1:5000/admin/login) — sources, leads, content items, snapshots, **Poll now**.

Defaults: SQLite in `instance/synapse.db`. For Postgres, set `DATABASE_URL` (and install `psycopg[binary]`). See [synapse_scope.md](synapse_scope.md) for env vars.

Production-style: `gunicorn wsgi:app` (or similar) with `SECRET_KEY`, `ADMIN_PASSWORD` / `ADMIN_PASSWORD_HASH`, and a real database URL.

## Local LLM (Ollama)

Full install steps, curl smokes, and env vars are in **[docs/ollama.md](docs/ollama.md)**.

Quick check without Python:

```bash
./scripts/ollama_smoke.sh
```

## Tests

Install dev dependencies (use a venv on PEP 668–managed Python, e.g. Homebrew):

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
```

- **Exclude** Ollama integration tests (e.g. in CI without a daemon):

  ```bash
  pytest -m "not ollama"
  ```

- **Only** Ollama API checks (skips cleanly if Ollama is off or models are missing):

  ```bash
  pytest -m ollama
  ```

Fast local run excluding slow generates:

```bash
pytest -m "ollama and not slow"
```

`tests/test_ollama_install.py` uses `@pytest.mark.ollama`; the generate probe is additionally marked `@pytest.mark.slow` because model load can exceed a normal unit-test budget.

## Pytest markers

| Marker | Meaning |
|--------|---------|
| `ollama` | Hits `OLLAMA_HOST` (`http://127.0.0.1:11434` by default). |
| `slow` | Long timeouts (model load). |

Markers are registered in [pytest.ini](pytest.ini).
