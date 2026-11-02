.PHONY: install test lint format serve run clean docker-up docker-down

PYTHON ?= ./.venv/bin/python3
PYTEST ?= ./.venv/bin/pytest
UVICORN ?= ./.venv/bin/uvicorn
RUFF ?= ./.venv/bin/ruff

install:
	$(PYTHON) -m pip install -e . --no-build-isolation

test:
	$(PYTEST) -v --durations=10

lint:
	$(PYTHON) -m py_compile src/complaintiq/serving/app.py
	@echo "All Python source files pass byte-compilation syntax checks."

format:
	$(RUFF) format src tests

serve:
	$(UVICORN) complaintiq.serving.app:app --host 0.0.0.0 --port 8000 --reload

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down
