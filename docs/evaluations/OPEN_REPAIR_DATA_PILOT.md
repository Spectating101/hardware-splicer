# Open Repair Alliance repair-case discovery (pilot)

Use the **actual CSV**, not GitHub's Git LFS pointer, from https://openrepair.org/open-data/downloads/ . Run `PYTHONPATH=src python -m hardware_splicer.open_repair_candidates --csv /path/to/OpenRepairData_v0.3_aggregate_202607_eee.csv --category Printer`.

The tool produces category-specific counts for recorded problems, barriers and outcomes. Results are **community repair-attempt observations**, not diagnosis, engineering specifications, a representative success probability, market demand, product identity, a right to purchase or physical safety proof. Limited scans are marked truncated, so their distributions must not be generalized.

The published ORDS v0.3 EEE dataset is licensed **CC BY-SA 4.0**, last updated October 2026 with observations to July 2026. Raw donor descriptions/records are never copied into Git by this tool. To use this in a Hardware Splicer mission, an operator must separately bind a specific physical device, characterize it, and satisfy all mission-level acceptance gates. No wiring, actuation, repair or fabrication is automated here.
