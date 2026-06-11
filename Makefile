.PHONY: up down migrate test lint

up:
	docker compose up -d --build

down:
	docker compose down

migrate:
	cd backend && alembic upgrade head

test:
	cd backend && pytest tests/ -v

lint:
	cd backend && ruff check . && mypy app --ignore-missing-imports
