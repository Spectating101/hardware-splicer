# Software for the eventual Fielddeck 7

The digital package does not contain a booted ARM image. No emulator or real Pi was available. Script syntax and the harmless plan modes were checked on the workstation; boot, touchscreen, networking and driver operation remain physical bring-up work.

Use the official **Raspberry Pi OS 64-bit Desktop**, Debian 13 Trixie, release **6 October 2026**, kernel 6.18, for Pi 4B. The official download page listed image SHA256 `976766570bee2aaf3047dd78649cfe82abb8fe9687b7f15030cd533ba4e9f7a9`. This is a publisher checksum reference, not a locally downloaded/verified image. Recheck it if the image changes. [Publisher download page](https://www.raspberrypi.com/software/operating-systems/).

Use Raspberry Pi Imager to choose Pi 4, set a unique user, keyboard layout, Wi-Fi country/network, and SSH public key. Do not store credentials in the repository. The selected keyboard uses a US layout. Configure Ethernet or Wi-Fi according to the network in use. [Official installation instructions](https://www.raspberrypi.com/documentation/computers/getting-started.html).

The 7-inch panel is physically portrait, rotated 90 degrees in this case. With the current desktop, use **Preferences → Control Centre → Screens → DSI-1 → Orientation**, select the landscape direction matching the cable end, Apply and retain it. This supplies a landscape 1280 × 720 desktop. Check touches at all four corners. Pi 4 auto-detects the official display; use the standard 15-way FFC. [Official display instructions](https://www.raspberrypi.com/documentation/accessories/touch-display-2.html).

Run `bash setup.sh` to see the package plan. On the actual selected Pi only, `bash setup.sh --apply` installs terminal tools and copies this package's local build references into `~/Fielddeck/docs`. It needs internet access once; the copied files and installed man pages then work offline. The package does not claim to bundle an offline encyclopedia or every electronics datasheet.

SSH from another computer with `ssh <configured-user>@<Pi-address>`, or use the cyberdeck to connect to another machine with the same command. Use `tmux` for persistent terminal sessions. `picocom`/`minicom` can service a future USB serial adapter, but that adapter is an optional accessory, absent from this BOM and power model. GPIO instrumentation, a DMM and an oscilloscope are not capabilities of this cyberdeck on their own.

Use `bash healthcheck.sh --capture` on the eventual Pi to record basic evidence. Then test keyboard keys, touchscreen corners, SSH in both directions, offline document access, graceful shutdown, and sustained ordinary workload with `vcgencmd get_throttled`/temperature monitoring. A bank/cable voltage/current measurement and a complete runtime discharge are still required to replace the scenario estimates. No software config can turn the bank's 5 V 3 A output into a 30 W supply at 5 V.
