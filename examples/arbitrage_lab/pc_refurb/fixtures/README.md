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
