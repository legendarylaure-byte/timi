#!/bin/bash
set -euo pipefail

OLLAMA_URL="${OLLAMA_BASE_URL:-http://host.docker.internal:11434}"
MODEL="${OLLAMA_MODEL:-qwen3.5:9b}"
WAIT_SECONDS="${OLLAMA_WAIT_SECONDS:-180}"
POLL="2"

echo "[start] Waiting for Ollama at ${OLLAMA_URL} ..."
elapsed=0
until curl -sf --max-time 3 "${OLLAMA_URL}/api/version" >/dev/null 2>&1; do
  if [ "$elapsed" -ge "$WAIT_SECONDS" ]; then
    echo "[start] ERROR: Ollama not reachable after ${WAIT_SECONDS}s at ${OLLAMA_URL}"
    echo "[start] Continuing with startup anyway (factory/fallback mode)."
    break
  fi
  sleep "$POLL"
  elapsed=$((elapsed + POLL))
done
echo "[start] Ollama reachable (waited ${elapsed}s)."

if curl -sf --max-time 3 "${OLLAMA_URL}/api/version" >/dev/null 2>&1; then
  echo "[start] Ensuring model '${MODEL}' is present ..."
  if ! curl -sf --max-time 5 "${OLLAMA_URL}/api/tags" | grep -q "\"${MODEL}\""; then
    echo "[start] Model '${MODEL}' missing — pulling now (this may take a while) ..."
    curl -sf --max-time 1800 -X POST "${OLLAMA_URL}/api/pull" -d "{\"name\":\"${MODEL}\"}" >/dev/null 2>&1 || echo "[start] WARN: pull failed (fallback to Gemini at runtime)"
  else
    echo "[start] Model '${MODEL}' already present."
  fi
else
  echo "[start] WARN: Ollama unreachable — skipping model ensure (runtime fallback to Gemini)."
fi

echo "[start] Starting pipeline: python main.py"
exec python main.py
