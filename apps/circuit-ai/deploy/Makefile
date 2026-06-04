.PHONY: install dev test run docker clean demo

# Installation
install:
	pip install -r requirements.txt

dev:
	pip install -r requirements-dev.txt
	pre-commit install

# Development
run:
	uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

run-gradio:
	python src/ui/gradio_app.py

# Testing
test:
	pytest tests/ -v

test-cov:
	pytest tests/ --cov=src --cov-report=html

test-comprehensive:
	python scripts/test_comprehensive.py --category all

test-core:
	python scripts/test_comprehensive.py --category core

test-detection:
	python scripts/test_comprehensive.py --category detection

test-llm:
	python scripts/test_comprehensive.py --category llm

test-performance:
	python scripts/test_comprehensive.py --category performance

# Code quality
format:
	black src/ tests/
	ruff check --fix src/ tests/

lint:
	ruff check src/ tests/
	mypy src/

# Docker
docker-build:
	docker build -t circuit-ai .

docker-run:
	docker run -p 8000:8000 circuit-ai

# Demo
demo:
	python scripts/demo.py

demo-enhanced:
	python scripts/enhanced_demo_and_test.py --mode all

demo-tests:
	python scripts/enhanced_demo_and_test.py --mode tests

demo-showcase:
	python scripts/enhanced_demo_and_test.py --mode demos

demo-examples:
	python scripts/enhanced_demo_and_test.py --mode examples

demo-setup:
	python scripts/enhanced_demo_and_test.py --mode setup

# Cleanup
clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name "htmlcov" -exec rm -rf {} + 