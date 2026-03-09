# ─────────────────────────────────────────────────────────────────────────────
# Astro AI - Makefile
#
# Usage:
#   make <target> [ENV=dev]     # ENV defaults to "dev"
#
# Environments:
#   dev       env/.env.dev, bot/env/.env.dev
#   staging   env/.env.staging, bot/env/.env.staging
#   prod      env/.env.prod, bot/env/.env.prod
# ─────────────────────────────────────────────────────────────────────────────

ENV ?= dev

INFRA_ENV_FILE := env/.env.$(ENV)
BOT_ENV_FILE   := bot/env/.env.$(ENV)

INFRA_COMPOSE  := docker compose -f infra/docker-compose.yaml --env-file $(INFRA_ENV_FILE)
BOT_COMPOSE    := docker compose -f bot/docker-compose.yaml   --env-file $(BOT_ENV_FILE)

# ── Guards ────────────────────────────────────────────────────────────────────

.PHONY: check-infra-env check-bot-env

check-infra-env:
	@test -f $(INFRA_ENV_FILE) || (echo "ERROR: $(INFRA_ENV_FILE) not found" && exit 1)

check-bot-env:
	@test -f $(BOT_ENV_FILE) || (echo "ERROR: $(BOT_ENV_FILE) not found" && exit 1)

# ── Infra ─────────────────────────────────────────────────────────────────────

.PHONY: infra-up infra-down infra-logs infra-ps

infra-up: check-infra-env
	$(INFRA_COMPOSE) up -d
	@echo "Waiting for Postgres to be healthy..."
	@until docker inspect astro-pgdb --format='{{.State.Health.Status}}' 2>/dev/null | grep -q healthy; do sleep 1; done
	@docker exec -u postgres -i astro-pgdb psql \
		-d $(shell grep ^POSTGRES_DB $(INFRA_ENV_FILE) | cut -d= -f2) \
		< infra/init/astro-extensions.sql 2>/dev/null \
		&& echo "pgvector enabled"

infra-down: check-infra-env
	$(INFRA_COMPOSE) down

infra-logs: check-infra-env
	$(INFRA_COMPOSE) logs -f

infra-ps: check-infra-env
	$(INFRA_COMPOSE) ps

# ── Bot ───────────────────────────────────────────────────────────────────────

.PHONY: bot-up bot-down bot-logs bot-ps bot-build

bot-up: check-bot-env
	$(BOT_COMPOSE) up -d

bot-down: check-bot-env
	$(BOT_COMPOSE) down

bot-logs: check-bot-env
	$(BOT_COMPOSE) logs -f

bot-ps: check-bot-env
	$(BOT_COMPOSE) ps

bot-build: check-bot-env
	$(BOT_COMPOSE) up -d --build

# ── Combined ──────────────────────────────────────────────────────────────────

.PHONY: up down logs

up: check-infra-env check-bot-env
	$(INFRA_COMPOSE) up -d
	$(BOT_COMPOSE) up -d

down: check-infra-env check-bot-env
	$(BOT_COMPOSE) down
	$(INFRA_COMPOSE) down

logs:
	docker compose -f infra/docker-compose.yaml -f bot/docker-compose.yaml logs -f
