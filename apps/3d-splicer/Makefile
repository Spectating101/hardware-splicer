.PHONY: run run-docker build freeze test test-unit test-integration test-cov health install

install:
	./venv/bin/pip install -r requirements-core.txt

freeze:
	./venv/bin/pip freeze > requirements.lock

run:
	./venv/bin/uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

build:
	docker build -t 3d-splicer .

run-docker:
	docker run --rm -p 8000:8000 3d-splicer

test:
	./venv/bin/pytest tests/ -v

test-unit:
	./venv/bin/pytest tests/ -v -m "not integration"

test-integration:
	./venv/bin/pytest tests/ -v -m integration

test-cov:
	./venv/bin/pytest tests/ -v --cov --cov-report=html --cov-report=term

health:
	curl -s http://127.0.0.1:8000/health | python -m json.tool && \
	curl -s http://127.0.0.1:8000/health/geom | python -m json.tool
