.PHONY: setup setup-cadquery cleanup test doctor demo smoke test test-apps benchmark-backend audit-functional-delivery plant-qwen-pipeline score-intake-tiers verify verify-catalog verify-engine verify-netlist-engine verify-fab verify-casefiles verify-tier-c verify-geometry verify-splice salvage-demo splice-demo test-golden-intakes refresh-demo-data explore explore-all run-mcp export-catalog-build-ids splice-ui-install splice-ui-dev splice-ui-build splice-ui-serve verify-splice-v1 test-splice-product-v1 verify-product-v1 verify-ui-interface-smoke launch-prep-v1.1 release-verify-v1.1 verify-install-smoke verify-product-live-smoke verify-product-internal

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
	PYTHONPATH=src HARDWARE_SPLICER_SKIP_VISION_LIVE=1 HARDWARE_SPLICER_OFFLINE_SALVAGE=1 HARDWARE_SPLICER_OFFLINE_COMPOSE=1 HARDWARE_SPLICER_QWEN_SALVAGE=0 HARDWARE_SPLICER_SALVAGE_RESOLVE=heuristic HARDWARE_SPLICER_JLC_ENRICH=0 $(PYTHON) scripts/hardware_splicer_e2e.py

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
	HARDWARE_SPLICER_AUTOROUTE=0 HARDWARE_SPLICER_JLC_ENRICH=0 PYTHONPATH=src $(PYTHON) scripts/benchmark_backend_design.py

audit-functional-delivery:
	HARDWARE_SPLICER_AUTOROUTE=0 HARDWARE_SPLICER_JLC_ENRICH=0 HARDWARE_SPLICER_SKIP_VISION_LIVE=1 HARDWARE_SPLICER_OFFLINE_SALVAGE=1 HARDWARE_SPLICER_OFFLINE_COMPOSE=1 HARDWARE_SPLICER_QWEN_SALVAGE=0 HARDWARE_SPLICER_SALVAGE_RESOLVE=heuristic PYTHONPATH=src $(PYTHON) scripts/audit_functional_delivery.py --strict

plant-qwen-pipeline:
	python3 scripts/run_qwen_plant_pipeline.py

score-intake-tiers:
	PYTHONPATH=src HARDWARE_SPLICER_SKIP_VISION_LIVE=1 HARDWARE_SPLICER_OFFLINE_SALVAGE=1 HARDWARE_SPLICER_OFFLINE_COMPOSE=1 HARDWARE_SPLICER_OFFLINE_PHRASE_EXPAND=1 HARDWARE_SPLICER_QWEN_SALVAGE=0 HARDWARE_SPLICER_SALVAGE_RESOLVE=heuristic HARDWARE_SPLICER_QWEN_WORKSHOP=0 HARDWARE_SPLICER_SKIP_KICAD_STEP_EXPORT=1 $(PYTHON) scripts/score_intake_tiers.py

refresh-demo-data:
	HARDWARE_SPLICER_SKIP_VISION_LIVE=1 python3 scripts/refresh_demo_sample_data.py

verify-engine:
	HARDWARE_SPLICER_AUTOROUTE=0 HARDWARE_SPLICER_JLC_ENRICH=0 PYTHONPATH=src $(PYTHON) scripts/verify_engine.py

verify-netlist-engine:
	HARDWARE_SPLICER_AUTOROUTE=0 HARDWARE_SPLICER_JLC_ENRICH=0 PYTHONPATH=src $(PYTHON) scripts/verify_netlist_engine.py

export-catalog-build-ids:
	PYTHONPATH=src $(PYTHON) scripts/export_catalog_build_ids.py

verify-fab:
	HARDWARE_SPLICER_AUTOROUTE=0 HARDWARE_SPLICER_JLC_ENRICH=0 PYTHONPATH=src $(PYTHON) scripts/verify_fab.py --all

verify-casefiles:
	PYTHONPATH=src $(PYTHON) -m pytest tests/test_compile_casefile.py -q

verify-tier-c:
	HARDWARE_SPLICER_AUTOROUTE=0 HARDWARE_SPLICER_JLC_ENRICH=0 HARDWARE_SPLICER_SKIP_VISION_LIVE=1 HARDWARE_SPLICER_OFFLINE_SALVAGE=1 HARDWARE_SPLICER_OFFLINE_COMPOSE=1 HARDWARE_SPLICER_QWEN_SALVAGE=0 HARDWARE_SPLICER_SALVAGE_RESOLVE=heuristic PYTHONPATH=src $(PYTHON) scripts/audit_functional_delivery.py --strict
	PYTHONPATH=src HARDWARE_SPLICER_SKIP_VISION_LIVE=1 $(PYTHON) -m pytest tests/test_tier_c_delivery.py -q

verify-geometry:
	HARDWARE_SPLICER_AUTOROUTE=0 HARDWARE_SPLICER_JLC_ENRICH=0 PYTHONPATH=src $(PYTHON) scripts/verify_geometry.py

salvage-demo:
	HARDWARE_SPLICER_AUTOROUTE=0 HARDWARE_SPLICER_DRC_FIX_LOOP=1 PYTHONPATH=src $(PYTHON) scripts/salvage_bringup_demo.py --out /tmp/hs_salvage_bringup

splice-demo:
	HARDWARE_SPLICER_AUTOROUTE=0 HARDWARE_SPLICER_DRC_FIX_LOOP=1 HARDWARE_SPLICER_SKIP_VISION_LIVE=1 HARDWARE_SPLICER_OFFLINE_SALVAGE=1 PYTHONPATH=src $(PYTHON) scripts/splice_demo.py --case robot_drive_from_rc_toy --out /tmp/hs_splice_demo

verify-splice:
	HARDWARE_SPLICER_AUTOROUTE=0 HARDWARE_SPLICER_DRC_FIX_LOOP=1 HARDWARE_SPLICER_SKIP_VISION_LIVE=1 HARDWARE_SPLICER_OFFLINE_SALVAGE=1 PYTHONPATH=src $(PYTHON) scripts/verify_splice_demos.py --out /tmp/hs_splice_verify

splice-golden-loop:
	HARDWARE_SPLICER_AUTOROUTE=0 HARDWARE_SPLICER_DRC_FIX_LOOP=1 HARDWARE_SPLICER_SKIP_VISION_LIVE=1 HARDWARE_SPLICER_OFFLINE_SALVAGE=1 PYTHONPATH=src $(PYTHON) scripts/splice_golden_loop.py --out /tmp/hs_splice_golden_loop

verify-splice-loop:
	HARDWARE_SPLICER_AUTOROUTE=0 HARDWARE_SPLICER_DRC_FIX_LOOP=1 HARDWARE_SPLICER_SKIP_VISION_LIVE=1 HARDWARE_SPLICER_OFFLINE_SALVAGE=1 PYTHONPATH=src $(PYTHON) scripts/verify_splice_golden_loop.py

verify-splice-real-bench:
	HARDWARE_SPLICER_AUTOROUTE=0 HARDWARE_SPLICER_DRC_FIX_LOOP=1 HARDWARE_SPLICER_SKIP_VISION_LIVE=1 HARDWARE_SPLICER_OFFLINE_SALVAGE=1 PYTHONPATH=src $(PYTHON) scripts/verify_splice_real_bench.py

# Core v1 bar — run this before UI/packaging work. No npm, no splice-ui.
verify-splice-v1: doctor test-project-package verify-splice verify-splice-loop verify-splice-real-bench
	@echo "verify-splice-v1: engine + S2/S3 + project package — all passed"

test-splice-product-v1:
	PYTHONPATH=src $(PYTHON) -m pytest tests/test_splice_product_v1.py tests/test_design_studio_agent.py tests/test_canvas_module_pins.py tests/test_compose_agent_loop_salvage.py -q

verify-design-studio-agent: test-splice-product-v1
	@echo "verify-design-studio-agent: product API + agent compose spine passed"

# Internal product maturity bar: engine + UI build + product API tests.
verify-product-v1: verify-splice-v1 splice-ui-build test-splice-product-v1
	@echo "verify-product-v1: engine + splice-ui + product API — all passed"

verify-ui-interface-smoke:
	PYTHONPATH=src $(PYTHON) scripts/verify_ui_interface_smoke.py

release-verify-v1.1:
	bash scripts/release_verify_v1_1.sh

verify-install-smoke:
	bash scripts/verify_install_smoke.sh

verify-product-live-smoke:
	PYTHONPATH=src $(PYTHON) scripts/verify_product_live_smoke.py

# Full internal maturity: engine + UI + API tests + install + live job smoke.
verify-product-internal: verify-product-v1 verify-install-smoke verify-product-live-smoke
	@echo "verify-product-internal: all internal maturity checks passed"

pin-golden-live-evidence:
	QWEN_DISABLED=0 QWEN_OUT_OF_QUOTA=0 VISION_MONTHLY_USD_LIMIT=5 VISION_DAILY_USD_LIMIT=2 VISION_MAX_USD_PER_CALL=0.25 PYTHONPATH=src $(PYTHON) scripts/pin_golden_live_board_evidence.py

splice-golden-real:
	HARDWARE_SPLICER_AUTOROUTE=0 HARDWARE_SPLICER_DRC_FIX_LOOP=1 HARDWARE_SPLICER_SKIP_VISION_LIVE=1 HARDWARE_SPLICER_OFFLINE_SALVAGE=1 PYTHONPATH=src $(PYTHON) scripts/splice_golden_real.py --out /tmp/hs_splice_golden_real

vision-donor-smoke:
	PYTHONPATH=src $(PYTHON) scripts/generate_donor_test_image.py
	PYTHONPATH=src $(PYTHON) scripts/vision_donor_live_smoke.py

test-project-package:
	PYTHONPATH=src $(PYTHON) -m pytest tests/test_project_package.py tests/test_circuit_synthesis_bridge.py -q

verify-catalog:
	node scripts/verify_catalog_parity.cjs
	$(MAKE) export-catalog-build-ids

export-catalog-recipes:
	node scripts/export_catalog_recipes.cjs

export-engine-pcb-data:
	node scripts/export_engine_pcb_data.cjs

test-golden-intakes:
	PYTHONPATH=src HARDWARE_SPLICER_SKIP_VISION_LIVE=1 HARDWARE_SPLICER_OFFLINE_SALVAGE=1 HARDWARE_SPLICER_OFFLINE_COMPOSE=1 HARDWARE_SPLICER_QWEN_SALVAGE=0 HARDWARE_SPLICER_SALVAGE_RESOLVE=heuristic HARDWARE_SPLICER_JLC_ENRICH=0 $(PYTHON) -m pytest tests/test_golden_intake_compile.py tests/test_golden_catalog_direct.py -q

test-compose-scenarios:
	PYTHONPATH=src $(PYTHON) -m pytest tests/test_compose_scenarios.py -q

test-scratch-pipeline:
	PYTHONPATH=src $(PYTHON) -m pytest tests/test_scratch_pipeline.py -q

run-mcp:
	HARDWARE_SPLICER_AUTOROUTE=0 HARDWARE_SPLICER_JLC_ENRICH=0 PYTHONPATH=src $(PYTHON) -m hardware_splicer.mcp_server

splice-ui-install:
	cd apps/splice-ui && npm install

splice-ui-dev: splice-ui-install
	cd apps/splice-ui && npm run dev

splice-ui-build: splice-ui-install
	cd apps/splice-ui && npm run build

# Build UI + serve API and static frontend on one port (auditor / demo mode).
splice-ui-serve: splice-ui-build
	HARDWARE_SPLICER_SERVE_UI=1 PYTHONPATH=src $(PYTHON) -m uvicorn hardware_splicer.api:app --host 127.0.0.1 --port 8787

verify: cleanup doctor verify-catalog test test-golden-intakes benchmark-backend audit-functional-delivery score-intake-tiers verify-splice smoke
	@echo "Hardware-Splicer verify: all checks passed"
