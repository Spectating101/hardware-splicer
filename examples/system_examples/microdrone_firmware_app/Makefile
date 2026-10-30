# Out-of-tree Crazyflie app, safe under nested Kbuild invocation.
# Kbuild can invoke this Makefile from the upstream firmware working directory,
# so PWD and relative ../../ prefixes are NOT stable for source discovery.
HS_APP_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
CRAZYFLIE_BASE := $(abspath $(HS_APP_DIR)/../..)
OOT_CONFIG := $(HS_APP_DIR)/app-config

include $(CRAZYFLIE_BASE)/tools/make/oot.mk
