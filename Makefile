.PHONY: help install-backend install-frontend dev-backend dev-worker dev-frontend \
  test lint-backend lint-frontend migrate revision seed-admin up down logs pull-model

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install-backend: ## Create venv and install backend deps (incl. dev)
	cd backend && python3 -m venv .venv && . .venv/bin/activate && pip install -U pip && pip install -e ".[dev]"

install-frontend: ## Install frontend deps
	cd frontend && npm install

dev-backend: ## Run FastAPI with autoreload (local, needs Postgres/Redis running)
	cd backend && . .venv/bin/activate && uvicorn app.main:app --reload --port 8000

dev-worker: ## Run Celery worker (local)
	cd backend && . .venv/bin/activate && celery -A app.workers.celery_app worker --loglevel=INFO --pool=solo

dev-frontend: ## Run Next.js dev server (local)
	cd frontend && npm run dev

test: ## Run backend pytest suite (hermetic: sqlite + fakeredis)
	cd backend && . .venv/bin/activate && python -m pytest -q

lint-backend: ## Ruff check backend
	cd backend && . .venv/bin/activate && ruff check app tests scripts

lint-frontend: ## ESLint frontend
	cd frontend && npm run lint

migrate: ## Apply Alembic migrations
	cd backend && . .venv/bin/activate && alembic upgrade head

revision: ## Generate a new Alembic revision (REVISION_MSG="msg" make revision)
	cd backend && . .venv/bin/activate && alembic revision --autogenerate -m "$(REVISION_MSG)"

seed-admin: ## Create an admin user (ADMIN_EMAIL=... ADMIN_PASSWORD=... make seed-admin)
	cd backend && . .venv/bin/activate && python -m scripts.create_admin \
		--email "$(ADMIN_EMAIL)" --password "$(ADMIN_PASSWORD)" --full-name "$(ADMIN_NAME)"

up: ## Start full dev stack with Docker Compose
	docker compose up -d --build

down: ## Stop the dev stack
	docker compose down

logs: ## Tail dev stack logs
	docker compose logs -f --tail=100

pull-model: ## Pull the vision model into the Ollama container
	docker compose exec ollama ollama pull $(MODEL)