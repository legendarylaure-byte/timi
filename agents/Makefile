.PHONY: setup test lint docker-up docker-down clean help

help:
	@echo "Usage:"
	@echo "  make setup       Create venv + install deps"
	@echo "  make test        Run pytest tests"
	@echo "  make lint        Flake8 lint check"
	@echo "  make docker-up   Build & start Docker container"
	@echo "  make docker-down Stop Docker container"

setup:
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r requirements.txt
	@if [ "$(shell uname)" = "Darwin" ]; then \
		.venv/bin/pip install -r requirements-macos.txt; \
	fi
	@echo "  ✅ Setup complete — run: source .venv/bin/activate"

test:
	.venv/bin/pytest tests/ -v --tb=short

lint:
	.venv/bin/python -m flake8 utils/ models/ crew/ compliance/ main.py run_pipeline.py --max-line-length=300

docker-up:
	docker compose -f ../docker-compose.yml up -d --build

docker-down:
	docker compose -f ../docker-compose.yml down

clean:
	rm -rf .venv __pycache__ .pytest_cache
	find . -name "*.pyc" -delete
