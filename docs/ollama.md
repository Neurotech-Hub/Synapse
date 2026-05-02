# Ollama (local Llama-family models) — install & verification

Synapse speaks to Ollama over HTTP for **generate** (lead copy / JSON) and optionally **embeddings** (similarity later). These steps assume **macOS on Apple Silicon (M-series)**; Linux differs only in how you install the binary.

---

## 1. Install Ollama

**Option A — Desktop app**

1. Download from [ollama.com](https://ollama.com).
2. Open the app; it starts the daemon in the menu bar.

**Option B — Homebrew**

```bash
brew install ollama
ollama serve
```

Leave `ollama serve` running in a terminal, or arrange a LaunchAgent/`brew services` setup if you want it always on.

---

## 2. Confirm the API

Default base URL:

| Variable | Default |
|---------|---------|
| `OLLAMA_HOST` | `http://127.0.0.1:11434` |

List models:

```bash
curl -s "${OLLAMA_HOST:-http://127.0.0.1:11434}/api/tags" | jq .
```

You should see JSON with a `"models"` array (possibly empty until you pull a model).

---

## 3. Pull models

Synapse MVP expects a **small instruct** chat model plus (optional) an embedding model:

| Variable | Suggested pull | Purpose |
|---------|----------------|---------|
| `OLLAMA_MODEL` | `ollama pull llama3.2` | Text generation (`/api/generate`) |
| `OLLAMA_EMBED_MODEL` | `ollama pull nomic-embed-text` | Vectors (`/api/embeddings`) — optional |

On **8 GB** unified RAM, stick to **3B–8B-class** quantized models pulled by Ollama; **`llama3.2`** is a reasonable default. Override names via env vars if your team standardizes something else (`mistral`, `qwen2.5`, etc.).

Notes:

- Tag names shown in `/api/tags` look like `llama3.2:latest`. Matching is by **model base name** (`llama3.2`): see pytest helpers in [`tests/test_ollama_install.py`](../tests/test_ollama_install.py).

---

## 4. Manual smoke checks (curl)

**Non-stream generate**

Replace `MODEL` if you changed `OLLAMA_MODEL`:

```bash
HOST="${OLLAMA_HOST:-http://127.0.0.1:11434}"
MODEL="${OLLAMA_MODEL:-llama3.2}"

curl -s "${HOST}/api/generate" -d "{
  \"model\": \"${MODEL}\",
  \"prompt\": \"Reply with exactly: OK\",
  \"stream\": false
}"
```

Expect HTTP 200 and a JSON body containing a non-empty **`"response"`** field.

**Embeddings** (optional; requires `OLLAMA_EMBED_MODEL` pulled)

```bash
EMBED="${OLLAMA_EMBED_MODEL:-nomic-embed-text}"

curl -s "${HOST}/api/embeddings" -d "{
  \"model\": \"${EMBED}\",
  \"prompt\": \"test\"
}"
```

Expect HTTP 200 and an **`embedding`** array.

---

## 5. Shell smoke script

From repo root:

```bash
chmod +x scripts/ollama_smoke.sh   # once
OLLAMA_MODEL=llama3.2 ./scripts/ollama_smoke.sh
```

This mirrors the curl checks above and exits non-zero on failure.

---

## 6. Automated verification (pytest)

Install dev deps and run marked tests:

```bash
pip install -r requirements-dev.txt
pytest -m ollama
```

When Ollama is **stopped** or models are **missing**, tests **skip** with an explicit reason (safe for laptops and CI).

- **Exclude** Ollama tests in CI: `pytest -m "not ollama"` (see [`README.md`](../README.md)).

---

## 7. App configuration (later)

Wire the Flask / ingest layer with:

- `OLLAMA_HOST` — API base URL.
- `OLLAMA_MODEL` — default generate model name (base tag, as Ollama expects in JSON).
- `OLLAMA_EMBED_MODEL` — when you enable embeddings.

---

## Troubleshooting

| Symptom | What to try |
|---------|--------------|
| Connection refused | Start the app or `ollama serve`. |
| 404 model not found | `ollama pull <name>` matching `OLLAMA_MODEL`. |
| Timeouts | First inference can load weights for a minute; rerun. Close other GPU/RAM-heavy apps on 8 GB machines. |
| Wrong model in tests | Export `OLLAMA_MODEL` / `OLLAMA_EMBED_MODEL` to match pulled models.
