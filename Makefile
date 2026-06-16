.PHONY: setup setup-cadquery cleanup test doctor demo smoke test test-apps benchmark-backend audit-functional-delivery plant-qwen-pipeline score-intake-tiers verify verify-catalog verify-engine verify-netlist-engine salvage-demo test-golden-intakes refresh-demo-data explore explore-all run-mcp

ROOT_DIR := $(abspath .)
PYTHON ?= $(if $(wildcard $(ROOT_DIR)/.venv/bin/python),$(ROOT_DIR)/.venv/bin/python,python3)

setup:
	bash scripts/setup_demo.sh

setup-cadquery:
	bash scripts/setup_demo.sh
	$(PYTHON) -m pip install cadquery || apps/3d-splicer/.venv/bin/pip install cadquery

cleanup:
	bash scripts/cleanup_test_artifacts.sh

doctor:
	$(PYTHON) scripts/hardware_splicer.py doctor

demo:
	$(PYTHON) scripts/hardware_splicer.py demo --out /tmp/hardware_splicer_demo

smoke:
	PYTHONPATH=src $(PYTHON) scripts/hardware_splicer_e2e.py

test:
	PYTHONPATH=src HARDWARE_SPLICER_SKIP_VISION_LIVE=1 $(PYTHON) -m pytest -q

explore:
	PYTHONPATH=src HARDWARE_SPLICER_SKIP_VISION_LIVE=1 $(PYTHON) scripts/exploration_test.py

explore-all: explore test-apps
	@echo "explore-all complete"

SPLICER3D_PYTHON := $(if $(wildcard apps/3d-splicer/.venv/bin/python),$(abspath apps/3d-splicer/.venv/bin/python),$(PYTHON))

test-apps:
	cd apps/mecha-splicer && $(PYTHON) -m pytest -q
	cd apps/3d-splicer && $(SPLICER3D_PYTHON) -m pytest -q

test-apps-full:
	cd apps/circuit-ai && $(PYTHON) -m pip install -r requirements.txt && PYTHONPATH=. $(PYTHON) -m pytest -q
	cd apps/mecha-splicer && $(PYTHON) -m pytest -q
	cd apps/3d-splicer && $(SPLICER3D_PYTHON) -m pytest -q

benchmark-backend:
	PYTHONPATH=src $(PYTHON) scripts/benchmark_backend_design.py

audit-functional-delivery:
	PYTHONPATH=src $(PYTHON) scripts/audit_functional_delivery.py --strict

plant-qwen-pipeline:
	python3 scripts/run_qwen_plant_pipeline.py

score-intake-tiers:
	PYTHONPATH=src HARDWARE_SPLICER_SKIP_VISION_LIVE=1 $(PYTHON) scripts/score_intake_tiers.py

refresh-demo-data:
	HARDWARE_SPLICER_SKIP_VISION_LIVE=1 python3 scripts/refresh_demo_sample_data.py

verify-engine:
	HARDWARE_SPLICER_AUTOROUTE=0 HARDWARE_SPLICER_JLC_ENRICH=0 PYTHONPATH=src $(PYTHON) scripts/verify_engine.py

verify-netlist-engine:
	HARDWARE_SPLICER_AUTOROUTE=0 HARDWARE_SPLICER_JLC_ENRICH=0 PYTHONPATH=src $(PYTHON) scripts/verify_netlist_engine.py

salvage-demo:
	HARDWARE_SPLICER_AUTOROUTE=0 HARDWARE_SPLICER_DRC_FIX_LOOP=1 PYTHONPATH=src $(PYTHON) scripts/salvage_bringup_demo.py --out /tmp/hs_salvage_bringup

verify-catalog:
	node scripts/verify_catalog_parity.cjs

export-catalog-recipes:
	node scripts/export_catalog_recipes.cjs

export-engine-pcb-data:
	node scripts/export_engine_pcb_data.cjs

test-golden-intakes:
	PYTHONPATH=src HARDWARE_SPLICER_SKIP_VISION_LIVE=1 $(PYTHON) -m pytest tests/test_golden_intake_compile.py tests/test_golden_catalog_direct.py -q

test-compose-scenarios:
	PYTHONPATH=src $(PYTHON) -m pytest tests/test_compose_scenarios.py -q

test-scratch-pipeline:
	PYTHONPATH=src $(PYTHON) -m pytest tests/test_scratch_pipeline.py -q

run-mcp:
	HARDWARE_SPLICER_AUTOROUTE=0 HARDWARE_SPLICER_JLC_ENRICH=0 PYTHONPATH=src $(PYTHON) -m hardware_splicer.mcp_server

verify: cleanup doctor verify-catalog test test-golden-intakes benchmark-backend audit-functional-delivery score-intake-tiers smoke
	@echo "Hardware-Splicer verify: all checks passed"
