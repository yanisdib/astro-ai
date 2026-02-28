#!/usr/bin/env bash
set -euo pipefail

# Configure Astro Bot environment and dependencies
cd /workspaces/astro-ai/bot

sudo chown -R $(whoami):$(whoami) .

export POETRY_VIRTUALENVS_IN_PROJECT=true
export POETRY_CACHE_DIR="$PWD/.cache/pypoetry"

poetry config virtualenvs.in-project true --local
poetry config virtualenvs.create true --local

if [ ! -d ".venv" ]; then
    echo "[post-create] Creating .venv folder..."
    python3 -m venv .venv
fi

echo "[post-create] Upgrading internal tools to avoid Rust compilation..."
VENV_PY="./.venv/bin/python"
if [ -x "$VENV_PY" ]; then
  "$VENV_PY" -m pip install --upgrade pip setuptools wheel
else
  python3 -m pip install --upgrade pip setuptools wheel
fi

if [ ! -f "pyproject.toml" ]; then
  echo "[post-create] No pyproject.toml found. Initializing…"
  poetry init -n
  
  echo "[post-create] Adding baseline dependencies..."
  if [ -x "$VENV_PY" ]; then
    "$VENV_PY" -m pip install pydantic-core pydantic
  else
    python3 -m pip install pydantic-core pydantic
  fi
  
  poetry add twitchio==3.2.1 python-dotenv==1.0.1 openai==2.21.0 supabase==2.28.0 pgvector==0.4.2 langchain==1.2.10 "psycopg[binary,pool]==3.3.3" tiktoken==0.12.0 fastapi==0.129.1 uvicorn==0.41.0 redis==7.1.1 uuid6==2025.0.1
fi

echo "[post-create] Syncing dependencies..."
poetry install --no-interaction

echo "[post-create] Environment Check:"
poetry env info

echo "[post-create] Done. Your environment is ready. "