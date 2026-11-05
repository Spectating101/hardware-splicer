`smart_ata_usb_hdd_control_redacted.json` is a REAL `smartctl -a -j` capture (smartmontools 7.4) of an external
2 TB USB hard disk on the authorised control host, taken read-only with `-n standby`. Serial number and WWN are
redacted. It exists to test the ATA parser against the real format, including the packed raw value of attribute 9
(`Power_On_Hours`) that must NOT be used for power-on hours. It is a control/format fixture, not evidence about any
salvaged unit.

`smart_nvme_control_healthy_redacted.json` is a REAL `smartctl -a -j` capture of the control host's NVMe system drive
taken while it was healthy (critical_warning 0, 43 C). Five minutes later, under load, the same drive reported
critical_warning 2 (temperature flag, 82 C = its warning threshold); that second capture is the committed control
bundle `control_host_optiplex/bundle/smart_nvme0n1.json`, and is the real-world case behind the "temperature-only
flag is unknown, not fail" rule in `casefile.eval_smart`.

`memtester_laptop_real_clean.txt`, `memtester_laptop_real_head_raw.txt`, `stress_ng_laptop_real.txt` and
`thermal_laptop_real_60s.json` are REAL outputs of `memtester 4.6.0` (1 GiB x 2 loops, rc 0), `stress-ng 0.15.06`
(60 s, rc 0) and the collector's thermal sampler, from the owner's laptop (`control_host` role, not a salvaged unit).
The raw head keeps memtester's progress/backspace characters (the full raw file is 650 KB, so only 9 KB is kept); the
"clean" file is the same output with the character+backspace pairs removed. They pin the real format the parser must
read: 18 tests per loop, each ending `ok`, then `Done.`. Real memtester also prints "...trying mlock ...failed" in some
normal runs, so the word "failed" must not be treated as a memory failure.
