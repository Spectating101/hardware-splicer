# HS Pocket Terminal Lab — real SSH + touch interaction acceptance

**Research date:** 2026-11-08. **Goal:** build one useful, cost-efficient pocketable dual-touch programming device, and prove Hardware Splicer can make correct product engineering decisions. This does **not** constitute creating a consumer-electronics company.

This is the *first working terminal interaction* in this part of HS's cyberdeck work: a browser with an upper **xterm.js** screen and lower touchscreen-style software keyboard communicating through an **actual OpenSSH client** to a short-lived, sandboxed **OpenSSH server running on the Optiplex via localhost**. It was deliberately implemented by **reusing xterm.js** instead of writing an inferior VT100 renderer. The user can perform real shell actions, Nano code-editing, tmux control and reconnect.

**DO NOT mistake this for a CM4 device or two physically attached touchscreens.** Both virtual panels render inside one 1280×1440 Chrome viewport. Test input is synthetic Playwright touch events, not a human usability trial on two 5-inch screens. This experiment does not solve Winstar vendor drivers, DSI, batteries, mechanical assembly, budget or display mountings.

## Grounded results (runtime, not generated fixture output)

The actual browser-to-OpenSSH-to-sandbox session ran and verified:

| Test | Outcome |
|---|---|
| Tap on-screen `p` `w` `d` and `Enter` | Real sandbox returned `/work` |
| Real tmux session, tap **Ctrl+B**, **D** | Detached with actual tmux output |
| Open Nano, tap `h s Space t o u c h`, **Ctrl+O**, **Enter**, **Ctrl+X** | File persisted as **`hs touch\n`** |
| Open another Nano file, type `abc`, **Left, Left, x** | File persisted as **`axbc\n`** |
| `sleep 30` then tap **Ctrl+C** | Interrupted running shell command |
| Eight actual round trips via an octal-encoded unique printf token | **15.8 ms sample median**, **20.6 ms max / nearest-rank p95**, **loopback only** |
| Tap **Ctrl+D** then **Reconnect**, read saved file | New authenticated SSH session; workspace preserved |
| Change server's pinned host public key, reconnect via strict OpenSSH | Rejected with **Host key verification failed** |
| HTTP without bearer token / WebSocket wrong token / wrong Origin | All denied |
| Actual Linux kernel namespace, temporary host/user keys and shell | No GitHub/home credentials mounted; no sandbox network |
| Usable actual two-panel touch hardware / native Linux Winstar | **NOT TESTED** |
| Remaining physical thinness, quoted cost and physical power | **STILL BLOCKED** |

The captured [screenshot](evidence/touch_ssh_bench.png) is from a real Chrome browser after terminal interaction; its on-screen keyboard is browser-generated UI, not a photo of a fabricated device. [Machine-readable report](evidence/bench_results.json) lists sample measurements and explicit boundaries.

For the 2026-11-08 Optiplex sample, the touchscreen-like viewport held **115 terminal columns × 25 rows** on the upper surface. The benchmark produced **27 actual browser key-tap events** (not just JS-injected text), and saved two real files through Nano. The temporary files, SSH keys, sockets and executable demo process were deleted after the test. `tmux` detaches *within* the sandboxed connection; the isolated tmux server is NOT persistent across reconnect, although the workspace files are. Full Optiplex persistence needs a separately approved normal remote tmux session, outside this deliberately ephemeral fixture.

## Components reused, not reinvented

- [xterm.js](https://github.com/xtermjs/xterm.js) v6.0.0, [fit addon](https://github.com/xtermjs/xterm.js/tree/master/addons/addon-fit) v0.11.0, locally installed with committed npm lockfile. Renderer, ANSI/VT100 control and cell layout come from upstream.
- OpenSSH `sshd` and `ssh`, strict one-use ED25519 host-key pinning, no passwords or forwarding, local server only.
- Bubblewrap `bwrap` filesystem and network namespaces, disposable `/work`, no access to real home credentials. The sandbox requires Linux `/proc/sys/dev/tty/legacy_tiocsti=0` because traditional controlling terminal job control and Ctrl+C must work; the tool refuses to run otherwise. **Not a general-purpose hardened remote shell service.**
- GNU Nano and tmux. No rewritten terminal/editor.

`server.py` uses aiohttp only as a small loopback-only PTY/WebSocket bridge with per-run bearer token and origin restriction. On disconnect it closes the old process; on browser reload it opens a new temporary sandboxed SSH process.

## Reproduce on an authorized local Linux workstation

Prerequisites: `/usr/sbin/sshd`, `ssh`, `ssh-keygen`, `tmux`, `nano`, `bwrap` (user namespaces functional and legacy TIOCSTI disabled), Python `aiohttp`, `playwright`, and a Chrome/Chromium executable. Do **not** run on a public webserver; a web browser can execute programs in the limited sandbox. On the test host these were already installed.

```bash
cd examples/cyberdeck/workflow_lab
npm ci --prefix web
python3 server.py                  # prints a short-lived localhost-only URL
# Open the URL on the same workstation; no external access

# Actual browser, pinned SSH, Nano, tmux, RTT and security acceptance:
HS_CHROME_PATH=/usr/bin/google-chrome python3 run_e2e.py
```

If Python packages are missing, install in an isolated venv: `pip install aiohttp playwright`. System Chrome/Chromium is used by Playwright (no extra simulated device needed). `run_e2e.py` fails if actual browsers, SSH server, Bubblewrap or user namespace requirements are missing; it **never** fabricates a PASS. It creates a screenshot and timing report in `evidence/`. The exact output can differ slightly across hosts, browsers, CPU load and local SSH configuration.

## Next product decision

Software workflow: **first proof passed**. It demonstrates that the basic split-terminal/touch-keyboard model can interact with real tools, using open components. It **does not yet demonstrate** that typing on a tiny glass keyboard for 30 minutes is ergonomic, that a user would prefer it to a Fold4/used phone, or that physical CM4 dual-DSI can run this UI.

**Practical next hardware test:** first qualify one physically supported DSI panel and its independent touch input on a real development carrier. Run the same end-to-end typing/editing script, then test two connected panels and power/thermal load. If no panel pair fits the 18mm and full-cost targets economically, change architecture instead of hiding the shortfall in another CAD shell.

No spending, custom carrier fabrication, battery power-up or manufactured device is authorized by this software-only result.
