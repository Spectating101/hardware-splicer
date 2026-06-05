# KiCad PCB Fixtures

This folder contains a small third-party fixture set from the official KiCad demo projects. The files are pinned to KiCad source tag `9.0.2` so the local `kicad-cli 9.0.2` path can be tested without depending on a live upstream branch.

Fixtures are used for Hardware-Splicer board parsing and KiCad STEP export tests. They are not product designs owned by this repo.

Source:
- Repository: https://gitlab.com/kicad/code/kicad
- Ref: `9.0.2`
- License: `GPL-3.0-or-later`
- Local manifest: `SOURCE_MANIFEST.json`
- Local license copy: `LICENSE.GPLv3.txt`

Refresh with:

```bash
rtk python3 scripts/fetch_kicad_pcb_fixtures.py
```
