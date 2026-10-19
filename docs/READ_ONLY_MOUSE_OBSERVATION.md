# Opt-in read-only mouse button observation (Linux)

The host_mouse_observer module is a limited bridge between one
explicitly selected Linux evdev node and the normalized JSONL input schema
consumed by the existing intact-reuse software review adapter. This is not
automatic donor discovery, a hardware validation, an engineering measurement,
or authorization to fabricate, flash, power on or operate machinery.

## What it does

- Requires the operator to select an exact /dev/input/eventN node and pass
  the --consent-to-read-input flag. It never enumerates input devices.
- Opens one character node O_RDONLY, O_NONBLOCK, O_NOFOLLOW and O_CLOEXEC.
  The only ioctl is a read-only capability query requiring BTN_LEFT. It does
  not identify the model of the physical device.
- Emits only normalized connected, released, pressed and disconnected
  events for an operator-supplied nonidentifying alias and the left button.
  Keyboard activity, coordinates, other mouse buttons, original timestamps
  and device identity are not passed downstream.
- Refuses kernel synchronization loss, unexpected values, truncated records,
  non-explicit node paths and malformed aliases.
- Has mandatory upper bounds of 300 seconds and 10,000 left-button events.
- Never uses EVIOCGRAB, never changes kernel device state, never injects
  input or runs commands, and does not write evidence into HS project records.

A captured event is a host observation, not a verified physical donor
contract. Even if the software adapter produces the symbolic action
"activate", this does not mean a built foot control or electrical component
is ready. Real mechanical return, button forces, travel, mounting geometry,
strain relief and service life remain unknown until independently checked.

## Explicit operator-only example

From a trusted checkout with the project on PYTHONPATH, after the operator
has independently selected and consented to observing an ordinary mouse:

    PYTHONPATH=src python -m hardware_splicer.host_mouse_observer \
      --device /dev/input/eventN \
      --alias donor_mouse \
      --seconds 10 \
      --max-events 20 \
      --consent-to-read-input

The program emits JSONL to stdout. It never chooses a node automatically.
If another program consumes stdout, it must preserve these fields unchanged
and honor the existing adapter's conservative state machine: a real release
is needed after connection before a press can produce a symbolic action.
No operating-system mouse injection is present.

## Tests without hardware

    PYTHONPATH=src python -m pytest -q tests/test_host_mouse_observer.py

Tests use synthetic native evdev records, stubbed select/read and ioctl,
and HS's real intact-reuse software adapter. They do not connect to,
enumerate, grab, alter or read any physical /dev/input device. Validation
of a genuine donor and its real output mapping is deferred until explicit
human consent to a specific nonhazardous specimen and node.
