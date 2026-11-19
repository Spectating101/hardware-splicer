# Circuit-AI Launch Runbook: Execution Guide

## 1. Create the Viral Asset (The Video)
**Goal:** A 60-second "Show, Don't Tell" clip.

*   [ ] **Setup:** Run `npm run dev` (Frontend) and `uvicorn src.api.enhanced_api:app` (Backend).
*   [ ] **Record Screen:**
    1.  **0:00:** Show the **Spatial Interface** (Dark mode, Glass panels).
    2.  **0:10:** Drag the **"Visual Clarity"** slider. Show components exploding in 3D.
    3.  **0:25:** Open **Command Palette** (`Cmd+K`). Type "Optimize layout for manufacturing."
    4.  **0:35:** Show the **Green Ghost** wireframes appearing.
    5.  **0:50:** Click **Fabrication Mode** (Printer Icon). Show the G-Code generating.
*   [ ] **Post:** Title: *"I built an AI that acts like Iron Man's Jarvis for PCBs."*

## 2. Deploy the MCP Server (The Product)
**Goal:** Let Claude/ChatGPT users use your tool.

*   [ ] **Prepare the Script:** Ensure `src/engines/circuit_ai_mcp.py` is executable.
*   [ ] **Create the Configuration:**
    *   Add this to `README.md` for users:
    ```json
    {
      "mcpServers": {
        "circuit-ai": {
          "command": "python",
          "args": ["src/engines/circuit_ai_mcp.py"],
          "env": {
            "CEREBRAS_API_KEY": "YOUR_KEY_HERE"
          }
        }
      }
    }
    ```
*   [ ] **Submit:** Push to GitHub. Submit URL to **Glama** or **Smithery.ai**.

## 3. The Community Drop (The Users)
**Goal:** Get your first 100 stars/users.

*   **Hackaday.io:**
    *   Create Project.
    *   Upload `USER_SCENARIOS.md` as the description.
    *   Upload the Demo Video.
*   **Reddit (r/HardwareHacking):**
    *   Post Title: *"I open-sourced a tool that uses Llama-3 to reverse-engineer broken PCBs."*
    *   Link to GitHub.

## 4. The "Arbitrage" Test (The Business)
**Goal:** Make your first $100 profit.

*   [ ] **Source:** Buy a broken **Gogoro Controller** or **Game Boy** (approx $15).
*   [ ] **Fix:** Use the tool's **Manual Guide** to diagnose/repair it.
*   [ ] **Sell:** List on eBay for $100+.
*   [ ] **Document:** Write a blog post: *"How I turned $15 of trash into $100 using Circuit-AI."* (This is your best marketing).
