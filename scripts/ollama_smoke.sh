#!/usr/bin/env bash
# Mirrors docs/ollama.md curl smoke checks. Exit non-zero if Ollama is down or generates fail.

set -euo pipefail

HOST="${OLLAMA_HOST:-http://127.0.0.1:11434}"
HOST="${HOST%/}"
MODEL="${OLLAMA_MODEL:-llama3.2}"
EMBED="${OLLAMA_EMBED_MODEL:-nomic-embed-text}"

echo "== Ollama smoke: HOST=${HOST} MODEL=${MODEL} =="
echo "-- GET /api/tags"
if ! TAGS="$(curl -sS --fail --connect-timeout 3 "${HOST}/api/tags")"; then
  echo "FAILED: cannot reach ${HOST}/api/tags (is ollama running?)" >&2
  exit 1
fi
echo "${TAGS}" | head -c 500
echo "..."

echo "-- POST /api/generate (non-stream)"
GEN="$(curl -sS --fail --max-time 180 "${HOST}/api/generate" \
  -d "{\"model\":\"${MODEL}\",\"prompt\":\"Reply with exactly: OK\",\"stream\":false}")"
if ! echo "${GEN}" | grep -q '"response"'; then
  echo "FAILED: unexpected generate response shape" >&2
  echo "${GEN}" >&2
  exit 1
fi
RESP="$(echo "${GEN}" | python3 -c "import sys, json; print(json.load(sys.stdin).get('response',''))" 2>/dev/null || true)"
if [ -z "${RESP}" ]; then
  echo "FAILED: empty response field" >&2
  exit 1
fi
echo "generate ok (${#RESP} chars)"

echo "-- POST /api/embeddings (optional; skips if wrong status)"
STATUS="$(curl -sS --max-time 60 -o /tmp/ollama_embed.$$ -w '%{http_code}' \
  "${HOST}/api/embeddings" \
  -d "{\"model\":\"${EMBED}\",\"prompt\":\"test\"}" || echo "000")"
if [ "${STATUS}" = "200" ]; then
  if ! grep -q '"embedding"' /tmp/ollama_embed.$$ 2>/dev/null; then
    echo "FAILED: embeddings body missing embedding key" >&2
    rm -f /tmp/ollama_embed.$$
    exit 1
  fi
  echo "embeddings ok (${EMBED})"
else
  echo "embeddings skipped (HTTP ${STATUS}; pull '${EMBED}' to enable)"
fi
rm -f /tmp/ollama_embed.$$

echo "== smoke passed =="
