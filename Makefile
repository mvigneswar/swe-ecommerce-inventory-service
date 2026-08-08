# Convenience targets for local development and deployment.
# Run `make help` to list them.

.PHONY: help setup install serve compose-up compose-down compose-logs seed test benchmark clean

help:
	@echo "Targets:"
	@echo "  setup        Create venv and install dependencies"
	@echo "  install      Install dependencies into the existing venv"
	@echo "  serve        Run the API locally (MySQL + Redis from docker compose)"
	@echo "  compose-up   Build and start the whole stack (api + mysql + redis)"
	@echo "  compose-down Stop the stack"
	@echo "  compose-logs Tail logs from every container"
	@echo "  seed         Insert 200 demo products into the catalog"
	@echo "  test         Run the test suite"
	@echo "  benchmark    Measure cached vs uncached latency"
	@echo "  clean        Remove caches and the venv"

setup:
	python -m venv venv
	.\venv\Scripts\python.exe -m pip install --upgrade pip
	.\venv\Scripts\python.exe -m pip install -r requirements.txt

install:
	.\venv\Scripts\python.exe -m pip install -r requirements.txt

serve:
	.\venv\Scripts\python.exe app.py

compose-up:
	docker compose up -d --build

compose-down:
	docker compose down

compose-logs:
	docker compose logs -f

seed:
	.\venv\Scripts\python.exe scripts/seed_data.py --count 200

test:
	.\venv\Scripts\python.exe -m pytest

benchmark:
	.\venv\Scripts\python.exe scripts/benchmark.py --runs 50

clean:
	-rmdir /s /q venv 2>nul
	-for /d /r . %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d"
	-del /s /q .pytest_cache 2>nul
