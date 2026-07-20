# Compatibility wrapper until the legacy Makefile target is folded into the
# canonical product composition. GNU make prefers GNUmakefile over Makefile.
# All normal goals delegate to the existing Makefile unchanged; the single
# product-preview goal launches the API that includes durable projects.

ifeq ($(strip $(MAKECMDGOALS)),splice-ui-serve)
ROOT_DIR := $(abspath .)
PYTHON ?= $(if $(wildcard $(ROOT_DIR)/.venv/bin/python),$(ROOT_DIR)/.venv/bin/python,python3)

.PHONY: splice-ui-serve
splice-ui-serve:
	$(MAKE) -f Makefile splice-ui-build
	HARDWARE_SPLICER_SERVE_UI=1 PYTHONPATH=src $(PYTHON) -m uvicorn hardware_splicer.product_api:app --host 127.0.0.1 --port 8787
else
include Makefile
endif
