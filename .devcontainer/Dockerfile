FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl ca-certificates bash build-essential \
    && rm -rf /var/lib/apt/lists/*

ENV POETRY_VERSION=1.8.3 POETRY_VIRTUALENVS_CREATE=false PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1
RUN pip install --upgrade pip && pip install "poetry==${POETRY_VERSION}"

WORKDIR /workspaces
