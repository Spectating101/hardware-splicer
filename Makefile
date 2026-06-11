.PHONY: setup doctor demo smoke test test-apps benchmark-backend audit-functional-delivery plant-qwen-pipeline score-intake-tiers verify refresh-demo-data explore

PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)

setup:
	bash scripts/setup_demo.sh

doctor:
	$(PYTHON) scripts/hardware_splicer.py doctor

demo:
	$(PYTHON) scripts/hardware_splicer.py demo --out /tmp/hardware_splicer_demo

smoke:
	PYTHONPATH=src $(PYTHON) scripts/hardware_splicer_e2e.py

test:
	PYTHONPATH=src HARDWARE_SPLICER_SKIP_VISION_LIVE=1 pytest -q

explore:
	PYTHONPATH=src HARDWARE_SPLICER_SKIP_VISION_LIVE=1 $(PYTHON) scripts/exploration_test.py

test-apps:
	cd apps/circuit-ai && pytest -q
	cd apps/mecha-splicer && pytest -q
	cd apps/3d-splicer && pytest -q

benchmark-backend:
	python3 scripts/benchmark_backend_design.py

audit-functional-delivery:
	python3 scripts/audit_functional_delivery.py --strict

plant-qwen-pipeline:
	python3 scripts/run_qwen_plant_pipeline.py

score-intake-tiers:
	HARDWARE_SPLICER_SKIP_VISION_LIVE=1 python3 scripts/score_intake_tiers.py

refresh-demo-data:
	HARDWARE_SPLICER_SKIP_VISION_LIVE=1 python3 scripts/refresh_demo_sample_data.py

verify: doctor test benchmark-backend audit-functional-delivery score-intake-tiers
	@echo "Hardware-Splicer verify: all checks passed"
