# User Story: The Layman's Repair Journey
**Scenario:** "The Broken Retro Console"
**User:** Alex, a hobbyist with zero engineering degree.
**Problem:** Found an old Game Boy Color in the attic. It turns on, but the sound doesn't work.

---

### 1. The "See" (Visual Experience)
Alex opens Circuit-AI on his laptop. He doesn't see a spreadsheet or a CAD grid.
*   **The Vibe:** It looks like a video game. A dark, sleek 3D void ("Spatial Glass").
*   **The Action:** He holds the Game Boy's circuit board up to his webcam.
*   **The AR Magic:** On screen, the video feed is overlaid with a glowing blue digital twin.
    *   A **Red Box** locks onto a small black cylinder.
    *   A floating label pops up: *"WARNING: Leaking Capacitor (C38)."*

**What Alex Thinks:** *"Whoa, it found the problem instantly. It's that leaking battery-looking thing."*

---

### 2. The "Use" (Interaction)
Alex doesn't know what "C38" is or how to solder.
*   **The Command Palette:** He presses `Cmd+K` (like searching on a Mac) and a floating bar appears.
*   **The Query:** He types exactly what he thinks: *"How do I fix the sound?"*
*   **The AI Response:** The system doesn't give him a schematic. It enters **"Guide Mode"**.
    *   **Step 1:** The 3D view zooms into C38.
    *   **Instruction:** *"This audio capacitor has failed. We need to replace it with a 100uF Electrolytic Capacitor."*
    *   **The Button:** A prominent button appears: **[GENERATE REPAIR PLAN]**.

**What Alex Thinks:** *"Okay, I just need to swap this part. The system knows what to do."*

---

### 3. The "Help" (Value & Execution)
Alex clicks **[GENERATE REPAIR PLAN]**. This is where the backend engines we built kick in, but Alex doesn't see "G-Code."

*   **Visual Confidence:** The screen shows a "Ghost" animation (Green Wireframe) of a robotic arm moving in to desolder the part. This is the **Safety Check** visualized.
*   **The Execution:**
    *   If Alex has the **Dum-E Robot**: He clicks **[EXECUTE]**. The robot wakes up, moves to the board, and points exactly to the bad leg.
    *   If Alex is **Manual**: The system highlights the pin in bright pink. *"Touch your soldering iron HERE for 3 seconds."*

**The Result:**
1.  **Confidence:** Alex didn't have to read a datasheet to know C38 was 100uF. The **Generative Agent** figured that out.
2.  **Safety:** The system warned him C38 is polarized (it has a + and - side), preventing him from installing it backward and causing a fire.
3.  **Success:** The Game Boy sound works.

---

### Summary of Value
*   **Before Circuit-AI:** Alex throws the Game Boy away or pays a shop $100.
*   **With Circuit-AI:** Alex feels like Tony Stark. He fixed a complex electrical issue just by pointing a camera and asking "How do I fix this?"
