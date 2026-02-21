#!/usr/bin/env bash
set -euo pipefail

cd /workspaces/astro-ai

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
  
  poetry add twitchio uuid6 openai supabase psycopg[binary] pgvector langchain redis python-dotenv tiktoken fastapi uvicorn
fi

echo "[post-create] Syncing dependencies..."
poetry install --no-interaction

echo "[post-create] Environment Check:"
poetry env info

echo "[post-create] Done. Your environment is ready. Happy coding! 🚀 "