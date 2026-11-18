# Hermes Sentinel: atalhos de desenvolvimento. `make help` lista tudo.
SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help

PY      := backend/.venv/bin/python
JS_PM   := $(shell command -v bun >/dev/null 2>&1 && echo bun || echo npm)
JS_RUN  := $(if $(filter bun,$(JS_PM)),bun run,npx)

.PHONY: help setup setup-kind dev test test-backend test-web lint lint-backend lint-web \
        format typecheck audit openapi check clean

help: ## Lista os comandos
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*##/ {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup: ## Instala backend (venv), frontend e cria o .env
	scripts/install-fedora.sh

setup-kind: ## setup + kubectl e kind para um cluster local
	scripts/install-fedora.sh --with-kind

dev: ## Sobe backend (:8000) e frontend (:3000)
	scripts/start.sh

test: test-backend test-web ## Roda todos os testes

test-backend: ## Testes do backend (pytest)
	cd backend && .venv/bin/python -m pytest

test-web: ## Testes do frontend (vitest)
	$(JS_RUN) vitest run

lint: lint-backend lint-web ## Lint de tudo

lint-backend: ## ruff (lint + formatação)
	cd backend && .venv/bin/ruff check . && .venv/bin/ruff format --check .

lint-web: ## ESLint + Prettier
	$(JS_RUN) eslint .
	$(JS_RUN) prettier --check "src/**/*.{ts,tsx,css}"

typecheck: ## TypeScript sem emitir
	$(JS_RUN) tsc --noEmit

format: ## Formata backend e frontend
	cd backend && .venv/bin/ruff check . --fix && .venv/bin/ruff format .
	$(JS_RUN) prettier --write "src/**/*.{ts,tsx,css}"

audit: ## Vulnerabilidades conhecidas nas dependências Python
	cd backend && .venv/bin/pip-audit -r requirements.txt --timeout 60

openapi: ## Exporta o contrato da API para docs/api/openapi.json
	cd backend && .venv/bin/python -m scripts.export_openapi ../docs/api/openapi.json

check: lint typecheck test ## Tudo o que o CI roda (antes de abrir PR)

clean: ## Remove caches e builds locais
	rm -rf .output dist coverage backend/.pytest_cache backend/.ruff_cache backend/htmlcov
	find backend -name __pycache__ -type d -prune -exec rm -rf {} +
