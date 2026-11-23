# Circuit-AI: The "Dum-E" Interface Concept

**Vision:** A physical-digital bridge where an AI Agent (Circuit-AI) uses a Robotic Arm (Dum-E) to inspect, probe, and repair electronics, controlled via a "Mission Control" UI.

## 1. The Workflow

The user does not "use software." The user **collaborates with a robot**.

### Phase 1: Alignment (The "Handshake")
*   **User Action:** Places physical PCB on the workbench.
*   **System Action:** Overhead camera identifies the board ID and orientation.
*   **UI Display:** Overlays the **3D Digital Twin** (from the CAD files) onto the **Live Video Feed**.
*   **Result:** The system knows that pixel (X,Y) in the video corresponds to Component `U1` Pin `1` in the schematic.

### Phase 2: Autonomous Scan
*   **System Action:** "Vision Engine" scans for anomalies (burns, missing parts).
*   **UI Display:** Highlights suspicious areas in **Red** on the 3D Twin.
*   **Agent Feed:** "Detected discoloration on R14. Requesting physical probe to verify resistance."

### Phase 3: Physical Intervention (Dum-E)
*   **User Command:** "Go ahead, Dum-E." (or Auto-Approve mode).
*   **Robot Action:** Dum-E moves the multimeter probe to the exact coordinates of R14's pads.
*   **UI Display:** 
    *   Shows a "Ghost Arm" on screen predicting the movement.
    *   Displays the **Live Value** (e.g., "9.8kΩ") floating next to the component.
    *   Compares it to the Design Value ("10kΩ") and marks it **PASS/FAIL**.

## 2. The Architecture

To achieve this, the UI needs three specific layers (which we started building):

1.  **The Digital Twin (Implemented):**
    *   *What it is:* The high-fidelity 3D model (PCB Viewport).
    *   *Why we need it:* The robot needs 3D coordinates (X, Y, Z), not just pixels. The CAD data provides the "Truth" of where things *should* be.

2.  **The "Live Link" (Next Step):**
    *   *What it is:* A WebSocket connection to the Python Backend (`enhanced_api.py`).
    *   *Function:* Streams real-time data (Probe values, Arm position, Camera frames) into the UI.

3.  **The Command Deck (Implemented):**
    *   *What it is:* The "Intelligence Feed" sidebar.
    *   *Why we need it:* It translates complex sensor data into human-readable choices ("Probe R14" vs "Ignore").

## 3. Why the Current Prototype Matters
The "Augmented Workbench" we just built is the **Cognitive Layer**. Without it, Dum-E is just a blind arm. It needs the **Design Context** (the 3D model) to know that "This blob of pixels is actually a Microcontroller, and Pin 1 is safe to touch."

## 4. Roadmap to "Iron Man"
1.  **Step 1 (Done):** Build the 3D Digital Twin UI.
2.  **Step 2 (Next):** Connect the "Inspection Mode" in UI to the `backend/vision.py` output.
3.  **Step 3 (Hardware):** Integreate Dum-E (G-Code/Serial) to accept coordinate commands from the UI.
