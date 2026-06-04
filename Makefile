.PHONY: demo smoke test test-apps

demo:
	python3 scripts/hardware_splicer.py demo --out /tmp/hardware_splicer_demo

smoke:
	python3 scripts/hardware_splicer_e2e.py

test:
	pytest -q

test-apps:
	cd apps/circuit-ai && pytest -q
	cd apps/mecha-splicer && pytest -q
	cd apps/3d-splicer && pytest -q
