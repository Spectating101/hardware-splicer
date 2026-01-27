# Text-to-Manufacturing: The Generative Code Workflow

**Objective:** Transform natural language ideas into manufacturable KiCad files (`.kicad_pcb`).

## 1. The Limitation of JSON
LLMs typically output JSON (BOM lists).
*   **Problem:** JSON doesn't contain geometry, routing, or placement data. You can't send JSON to a PCB Fab.
*   **Solution:** Don't ask for data. **Ask for Code.**

## 2. The "Code-First" Architecture
Instead of generating a description of the board, we generate the **Python Script** that builds the board.

### Phase 1: The Prompt (The Architect)
We ask the LLM to act as a **KiCad Python Scripter**.
> **Prompt:** "Write a Python script using the `pcbnew` library to create a board with an ATTiny85 at (100,100) connected to an LED."

### Phase 2: The Code (The Blueprint)
The LLM returns executable Python code:
```python
import pcbnew
board = pcbnew.BOARD()
u1 = board.AddFootprint('Package_DIP:DIP-8_W7.62mm', 'U1', ...)
# ... placement and routing logic ...
pcbnew.IO_MGR.SaveBoard('output.kicad_pcb', board)
```

### Phase 3: The Execution (The Builder)
*   **Action:** The system runs this script inside a Docker container with KiCad installed.
*   **Output:** A binary `.kicad_pcb` file.

## 3. Why this wins
1.  **Precision:** Code allows for exact coordinates (`x=105.5mm`).
2.  **Completeness:** The script handles footprints, nets, and tracks in one pass.
3.  **Manufacturability:** The output is a native KiCad file, ready for Gerber export and manufacturing at JLCPCB/PCBWay.

## 4. Implementation Status
*   **Verified:** We successfully generated a valid `pcbnew` script using Cerebras Llama-3.3.
*   **Next Step:** Build a "Sandboxed Runner" to execute these scripts safely and return the file download link.
