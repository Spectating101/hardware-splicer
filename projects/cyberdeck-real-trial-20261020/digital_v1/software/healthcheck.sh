#!/usr/bin/env bash
# Read-only future bring-up evidence; no host is reported as a working Pi.
set -euo pipefail
if [[ ${1:---plan} != --capture ]]; then
  printf 'Future Pi checks: model, OS, kernel, USB devices, DSI status, temperature, throttling and network addresses.\n'
  printf 'Use --capture on the Pi; this plan does not test hardware.\n'
  exit 0
fi
if [[ ! -r /proc/device-tree/model ]]; then
  printf 'No Raspberry Pi device tree on this host; physical checks unavailable.\n' >&2
  exit 2
fi
tr -d '\0' </proc/device-tree/model
printf '\n'
cat /etc/os-release
uname -a
lsusb
for status_file in /sys/class/drm/card*-DSI-*/status; do
  if [[ -r $status_file ]]; then
    printf '%s: %s\n' "$status_file" "$(cat "$status_file")"
  fi
done
if command -v vcgencmd >/dev/null; then
  vcgencmd measure_temp
  vcgencmd get_throttled
fi
ip -brief address
printf 'This capture does not measure input voltage, current, capacity or all touchscreen coordinates.\n'
