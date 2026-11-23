# Attribution and modification notice

Manufacturer: Shenzhen Creality 3D Technology Co., Ltd. Upstream repository: https://github.com/Creality3DPrinting/Ender-3 . Frozen commit: `88c7758cea9d0d00a54fdb238bedb3b33425f409` (2019-12-11).

The manufacturer files under `sources/` are unmodified copies, except the explicitly derived `interface.json`, `assembly_parts.json` and drawing preview PNG. `manifest.json` identifies each upstream path, URL, hash and byte count. The license text is preserved in `sources/LICENSE` and at the package root. This project grants no trademark rights or manufacturer endorsement.

New study material was authored on 2026-11-17: parameterized adapter, clamp and parking plate CAD; representative envelope assembly; scripts; vector artwork; G-code; renders; calculations; documentation; derived metadata; validation reports. It is licensed under GPL-3.0-only. Manufacturer files retain their original licensing and notices. New material is supplied without warranty. See [LICENSE](LICENSE).

The detailed E plate in the derived layout remains the unmodified manufacturer shape. New STEP/STL/GLB exports are accompanied by editable Python source and small manufacturer CAD inputs. The original E-plate SLDPRT is retained as its preferred CAD source. The full manufacturer assembly remains available at the exact pinned upstream URL and in the source working copy, while isolated generation uses the small extracted sources and metadata.

No manufacturer firmware is modified or redistributed as a new binary. `sources/Configuration.h` is an unmodified evidence copy. The sample uses the documented Marlin [linear move](https://marlinfw.org/docs/gcode/G000-G001.html), [absolute positioning](https://marlinfw.org/docs/gcode/G090.html), [hotend setpoint](https://marlinfw.org/docs/gcode/M104.html) and [bed setpoint](https://marlinfw.org/docs/gcode/M140.html) syntax. These references establish syntax, not compatibility with an untested physical machine.
