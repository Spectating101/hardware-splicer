import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import MechatronicsPanel from "./MechatronicsPanel.jsx";

describe("MechatronicsPanel", () => {
  it("shows empty state without mechatronics fields", () => {
    render(<MechatronicsPanel pkg={{ info: { project_name: "x" } }} />);
    expect(screen.getByTestId("mechatronics-panel-empty")).toBeInTheDocument();
  });

  it("renders firmware, mechanism, and authority from package", () => {
    render(
      <MechatronicsPanel
        pkg={{
          firmware_scaffold: {
            filename: "inspection_motion_fixture.ino",
            pins: { servo_pan: 18, servo_tilt: 19 },
            source: "// dual servo\nconst int PAN_PIN = 18;\n",
            claim_boundary: "Bring-up pins",
          },
          mechanism_pack: {
            kind: "pan_tilt",
            status: "ok",
            outputs: ["pt_base.scad", "enclosure.scad"],
          },
          mechatronics_authority: {
            current_authority_level: "no_mechatronics_authority",
            offline_pack: { ready: true },
            claim_boundary: "Starter pack",
          },
        }}
      />
    );
    expect(screen.getByTestId("mechatronics-panel")).toBeInTheDocument();
    expect(screen.getByTestId("mechatronics-mech-kind")).toHaveTextContent("pan_tilt");
    expect(screen.getByTestId("mechatronics-mech-status")).toHaveTextContent("ok");
    expect(screen.getByTestId("mechatronics-firmware-source")).toHaveTextContent("PAN_PIN");
    expect(screen.getByTestId("mechatronics-authority-level")).toHaveTextContent(
      "no_mechatronics_authority"
    );
  });
});
