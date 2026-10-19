# Try Hardware Splicer without hardware

This is one worked example: **could an old wired mouse become a foot button?**

Start it from the repository with Python 3.10 or later:

```bash
python scripts/demo_mouse_reuse.py
```

Open the local address it prints. No packages, account, API key or physical
device are needed. Stop the demonstration with Ctrl+C in its terminal.

## What you will see

1. **The starting item:** an ordinary wired mouse, described by public documents.
   The drawing is an illustration; we do not have a physical specimen.
2. **The goal:** use a foot press to trigger one computer action, without buying
   another controller board.
3. **The agent's proposal:** keep the mouse intact and let a separate pedal
   press its button. Moving the switch is an alternative with more unknowns.
   These options come from the saved agent study, not a new live model call.
4. **Something to try:** click **Press once**. The action count increases.
   Try **Hold down**, then **Keep holding**: it should not repeat. **Other mouse**
   should do nothing. After **Unplug & reconnect**, let go before pressing again.

The controls execute the exact Python program retained in the saved software
bundle. They are not a separate JavaScript imitation. Their input is pretend
button signals, and their output is a symbolic action—not a real keypress.
You can also download the saved program and its tests from the page.

## What this does not mean

We have not built a foot pedal, tested a real mouse, connected the program to a
real application, or measured whether the mechanism is safe and durable.
The saved agent planning and later software-package run were separate. This
page puts them side by side to make the work understandable; it does not turn
them into a new uninterrupted live-agent success.

The demo reads retained evidence and runs a hash-checked program. It does not
change a project, contact a provider, use a model allowance, or authorize any
physical work. It listens only on this computer and is not a production web
service. Requests replay a bounded event list; no new persistent store exists.

## Contributor checks

`tests/test_mouse_reuse_demo.py` covers the page, real Python replay, download,
cross-origin/host restrictions, malformed/oversized inputs, and refusal to load
changed bundle bytes. A browser walkthrough also verified the visible results:

| Action | Displayed total |
|---|---:|
| Press once | 1 |
| Hold down | 2 |
| Keep holding | 2 |
| Other mouse | 2 |
| Let go, then press once | 3 |
| Reconnect while held | 3; press disabled until release |
| Start again | 0; press enabled |

The page rendered without horizontal overflow at the checked browser's default
1920px viewport. No page-origin console errors were observed; unrelated browser
extension warnings are not application findings. A full-page screenshot attempt
timed out; a normal viewport screenshot succeeded. Small-screen rendering was
not separately browser-verified in this session.

Technical scope and retained output: [intact reuse guide](INTACT_INPUT_REUSE.md)
and [the saved software run](status/INTACT_REUSE_DELIVERABLE_2026-10-19.md).
