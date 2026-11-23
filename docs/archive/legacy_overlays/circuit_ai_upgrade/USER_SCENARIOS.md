# Circuit-AI User Scenarios: From Problem to Solution

This platform is not just for one type of user. It solves distinct problems for Startups, Hobbyists, and Educators.

---

## 1. The Hardware Startup Founder ("The Sprint")
**User:** Sarah, CTO of a wearable tech startup.
**Context:** It's 2 AM. The investor demo is tomorrow. The prototype board is getting dangerously hot.

*   **The Problem:** "I don't have time to re-read the 800-page datasheet for the PMIC. Why is it overheating?"
*   **The Workflow:**
    1.  Sarah opens Circuit-AI and loads her KiCad design.
    2.  She types into the **Command Palette**: *"Why is U3 overheating? Optimize thermal layout."*
    3.  **Circuit-AI Action:**
        *   **Analysis:** The AI spots that the copper pour area for the regulator is too small for 500mA current.
        *   **Ghost Mode:** It overlays a green wireframe showing a larger copper polygon and suggests adding 4 thermal vias.
*   **The Result:** Sarah modifies the board in 10 minutes based on the visual guide. The demo works perfectly.
*   **Value:** **Engineering Acceleration.** It acts as a Senior Engineer co-pilot.

---

## 2. The Retro-Tech Restorer ("The Detective")
**User:** Mark, a vintage computer collector.
**Context:** He just bought a "broken" Commodore 64 motherboard from eBay. It displays a black screen.

*   **The Problem:** "There are no schematics for this specific board revision. I see a blackened component, but the label is burned off."
*   **The Workflow:**
    1.  Mark points his webcam at the board in **Inspection Mode**.
    2.  He zooms into the burnt area.
    3.  **Circuit-AI Action:**
        *   **Inference:** The AI analyzes the traces. "This component connects the 5V rail to the Video Chip. Based on the footprint (0805) and location, this is likely a **Ferrite Bead** or **Fuse**, not a resistor."
        *   **Manual Guide:** It displays a step-by-step AR guide: *"1. Desolder pads. 2. Clean carbon. 3. Bridge with a 0-ohm jumper to test."*
*   **The Result:** Mark bridges the connection. The Commodore 64 boots up.
*   **Value:** **Forensic Intelligence.** It recovers lost information using logic.

---

## 3. The STEM Educator ("The Scaler")
**User:** Mr. Chen, High School Robotics Teacher.
**Context:** 30 students are building line-following robots. 15 of them aren't working.

*   **The Problem:** "I can't physically debug 30 circuits in a 45-minute class. The kids are frustrated."
*   **The Workflow:**
    1.  Students hold their robots up to the class tablet running Circuit-AI.
    2.  **Circuit-AI Action:**
        *   **Instant Scan:** It highlights errors in AR.
        *   *Student A:* "Red Box on D1: LED is backward (Anode/Cathode swapped)."
        *   *Student B:* "Red Box on R1: Wrong color bands (10k instead of 220 ohm)."
*   **The Result:** Students self-correct before raising their hands. Mr. Chen focuses on teaching logic, not debugging wiring.
*   **Value:** **Automated Supervision.** It acts as a TA (Teaching Assistant) for every student.

---

## Summary
| Persona | Key Pain | Circuit-AI Solution | Core Value |
| :--- | :--- | :--- | :--- |
| **Founder** | Time / Complexity | Generative Optimization | **Speed** |
| **Hobbyist** | Lack of Data | Forensic Inference | **Knowledge** |
| **Educator** | Volume / Attention | AR Debugging | **Scale** |
