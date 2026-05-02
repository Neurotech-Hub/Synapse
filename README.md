# Synapse

AI-assisted ingestion and lead workflow for Neurotech Hub.

**Documentation:** full env, schema, and product notes → [synapse_scope.md](synapse_scope.md)

---

## Run locally

### One-time setup

```bash
python3 -m venv .venv && source .venv/bin/activate   # omit `source …` on Windows
pip install -r requirements-dev.txt
export ADMIN_PASSWORD='local-only'   # or use ADMIN_PASSWORD_HASH (see below)
flask --app wsgi db upgrade          # first run and after migrations
```

### Start the server

```bash
python run.py    # http://127.0.0.1:5002 — or set SYNAPSE_PORT
```

**Alternative:**

```bash
SYNAPSE_PORT=5002 flask --app wsgi run --debug --host 127.0.0.1 --port 5002
```

**VS Code:** open [`run.py`](run.py), select the interpreter that uses `.venv`, then **Run Python File** or the **Synapse: run.py** launch config under Run and Debug.

### URLs

| Surface | Address |
|---------|---------|
| Public | [http://127.0.0.1:5002/](http://127.0.0.1:5002/) — URL submit (canonicalized; duplicates reported) |
| Admin | [http://127.0.0.1:5002/admin/](http://127.0.0.1:5002/admin/) — sources, leads, content items, snapshots, **Poll now** |

---

## Configuration

### Database

- Default: SQLite at `instance/synapse.db`.
- Postgres: set `DATABASE_URL` and install `psycopg[binary]`.
- Production: pair `gunicorn wsgi:app` (or similar) with `SECRET_KEY`, a real DB URL, and admin credentials below.

### Admin login & localhost

| Topic | Detail |
|-------|--------|
| Loopback bypass | With **`python run.py`** (`debug=True`) or **`flask … run --debug`**, **127.0.0.1** / **::1** can access `/admin` **without a password** (dev only). |
| Disable bypass | `export SYNAPSE_DISABLE_LOCAL_ADMIN_BYPASS=1` or run without Flask debug. |
| Bypass without debug | `SYNAPSE_TRUST_LOCALHOST=1` (still loopback-only). |
| Password env | **`ADMIN_PASSWORD`** is **stripped** on read so stray newlines from `.env` do not break login. Prefer **`ADMIN_PASSWORD_HASH`** (`werkzeug.security.generate_password_hash`) in shared/deployed setups. |

Non-debug deployments still require **`ADMIN_PASSWORD`** or **`ADMIN_PASSWORD_HASH`** unless you rely on the localhost bypass flags above.

---

## Ollama (optional enrichment)

Synapse talks to Ollama at **`OLLAMA_HOST`** (default `http://127.0.0.1:11434`). If nothing is listening, ingest continues without LLM-filled fields and **`pytest -m ollama`** tests skip.

**macOS — Homebrew**

```bash
brew install ollama
brew services start ollama    # login item — or foreground: `ollama serve`
ollama pull llama3.2          # matches default OLLAMA_MODEL; override if you prefer
```

After install, confirm `ollama` is on your PATH (e.g. `/opt/homebrew/bin/ollama` on Apple Silicon); open a new shell if the command is missing.

**Desktop app (macOS / Linux):** [ollama.com](https://ollama.com) — starts the API in the background.

- **Full runbook** (curl checks, env, troubleshooting): [docs/ollama.md](docs/ollama.md)
- **Quick shell check:** `./scripts/ollama_smoke.sh`

**Ingest flags (HTML + leads):**

| Variable | Effect |
|----------|--------|
| `SYNAPSE_HTML_PAGE_LLM` | When set to `0` / `false` / `no` / `off`, new `html_page` snapshots use visible-text heuristics only (no Ollama call). **Default** when unset: try Ollama first, then fall back. |
| `SYNAPSE_LEADS_INGEST` | Must be `1` / `true` / `yes` for Poll to create **LeadCandidate** rows for sources with **Lead source** checked (RSS entries and new **html_page** content items). |

Html pages still get **ContentItem** rows on each new SHA-256 snapshot; Ollama shapes `title`/`snippet` when enabled. Comparing “our” **Lead source** content against the rest is a later ranking step on top of this data.

---

## Tests

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
```

| Command | When |
|---------|------|
| `pytest` | Default suite (use a venv on PEP 668–managed Python, e.g. Homebrew). |
| `pytest -m "not ollama"` | CI or machines without Ollama. |
| `pytest -m ollama` | Only Ollama HTTP checks; skips if the daemon is down or models are missing. |
| `pytest -m "ollama and not slow"` | Ollama checks **without** the long generate probe. |

`tests/test_ollama_install.py` marks integration tests with `@pytest.mark.ollama`; the generate probe is also `@pytest.mark.slow` (model load can exceed a normal unit-test budget).

### Pytest markers

Registered in [pytest.ini](pytest.ini):

| Marker | Meaning |
|--------|---------|
| `ollama` | Calls `OLLAMA_HOST` (default `http://127.0.0.1:11434`). |
| `slow` | Long timeouts (e.g. model load). |
