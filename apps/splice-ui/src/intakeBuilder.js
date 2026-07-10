const PART_TYPES = [
  { id: "dc_motor", label: "DC motor / gearmotor" },
  { id: "microcontroller", label: "Microcontroller (ESP32, Arduino, …)" },
  { id: "donor_board", label: "Donor PCB / junk board" },
  { id: "tof_range", label: "Distance / ToF sensor" },
  { id: "battery_pack", label: "Battery pack" },
  { id: "relay", label: "Relay / switch" },
  { id: "pump", label: "Pump / actuator" },
  { id: "other", label: "Other part" },
];

function slugify(text) {
  return String(text || "my_hardware_project")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_|_$/g, "")
    .slice(0, 48) || "my_hardware_project";
}

function defaultPart() {
  return { name: "", type: "dc_motor", condition: "salvaged", notes: "" };
}

const INITIAL_WIZARD = {
  goal: "",
  projectName: "",
  mode: "salvage",
  parts: [defaultPart()],
  donorFixtureId: "",
  donorPhoto: null,
  donorVisionReport: null,
  visionEnrichedIntake: null,
  visionEnrichReport: null,
  visionLive: false,
  designStrategy: "llm",
  selectedModuleIds: ["usb-power-5v", "esp32-devkit", "dht22"],
  batteryVoltage: 7.4,
  runtimeMin: 20,
  massKg: "",
  answers: {},
  clarifier: null,
};

function stripDataUrl(dataUrl) {
  if (!dataUrl || typeof dataUrl !== "string") return "";
  const comma = dataUrl.indexOf(",");
  return comma >= 0 ? dataUrl.slice(comma + 1) : dataUrl;
}

function buildPartRow(row) {
  const part = {
    name: String(row.name || "").trim(),
    type: row.type || "other",
    condition: row.condition || "salvaged",
  };
  const notes = String(row.notes || "").trim();
  if (notes) part.notes = notes;
  if (row.type === "dc_motor") {
    part.voltage_v = 6.0;
    part.current_a = 0.45;
  }
  return part;
}

export function buildIntakeFromWizard(
  wizard,
  { donorFixtures = [], enrichedIntent = null, visionEnrichedIntake = null } = {},
) {
  const base = visionEnrichedIntake || enrichedIntent || {};
  const goal = String(wizard.goal || base.goal || "").trim();
  const projectName = slugify(wizard.projectName || goal);

  const intake = {
    ...base,
    project_name: projectName,
    goal,
    salvage_mode: wizard.mode === "salvage",
    available_parts: (wizard.parts || [])
      .map(buildPartRow)
      .filter((row) => row.name),
    constraints: {
      ...(base.constraints || {}),
      runtime_min: Number(wizard.runtimeMin) || 20,
      battery_voltage_v: Number(wizard.batteryVoltage) || 7.4,
    },
  };

  if (wizard.massKg) {
    intake.constraints.mass_kg = Number(wizard.massKg);
  }

  if (wizard.answers && Object.keys(wizard.answers).length) {
    intake.clarification_answers = { ...wizard.answers };
  }

  if (wizard.mode === "salvage" && wizard.donorFixtureId) {
    const fixture = donorFixtures.find((row) => row.id === wizard.donorFixtureId);
    if (fixture) {
      const boardRow = {
        board_id: fixture.board_id,
        board_name: fixture.label,
        functional_salvage: fixture.intake_path,
      };
      if (wizard.donorPhoto?.dataUrl) {
        boardRow.vision_source = {
          image_base64: stripDataUrl(wizard.donorPhoto.dataUrl),
          filename: wizard.donorPhoto.name || "donor_board.jpg",
          live: Boolean(wizard.visionLive),
          device_hint: fixture.label,
        };
      }
      intake.circuit = {
        mode: "circuit_board_system",
        boards: [boardRow],
      };
      intake.donor_board_vision = {
        enabled: true,
        live: Boolean(wizard.visionLive),
        merge_with_fixture: true,
        device_hint: fixture.label,
      };
      const hasDonor = intake.available_parts.some((row) => row.type === "donor_board");
      if (!hasDonor) {
        intake.available_parts.unshift({
          name: `${fixture.label} donor`,
          type: "donor_board",
          condition: "salvaged",
          notes: `Fixture: ${fixture.intake_path}`,
        });
      }
    }
  } else if (wizard.donorPhoto?.dataUrl) {
    intake.attachments = [
      {
        id: "donor_board_photo",
        kind: "donor_board",
        board_id: "donor_board",
        image_base64: stripDataUrl(wizard.donorPhoto.dataUrl),
        filename: wizard.donorPhoto.name || "donor_board.jpg",
      },
    ];
    intake.donor_board_vision = { enabled: true, live: Boolean(wizard.visionLive) };
  }

  if (wizard.donorVisionReport?.intake) {
    const merged = wizard.donorVisionReport.intake;
    if (merged.circuit) intake.circuit = merged.circuit;
    if (merged.evidence_notes) intake.evidence_notes = merged.evidence_notes;
  }

  return intake;
}

export function buildComposePayloadFromWizard(wizard, { enrichedIntent = null } = {}) {
  const goal = String(wizard.goal || enrichedIntent?.goal || "").trim();
  const constraints = {
    runtime_min: Number(wizard.runtimeMin) || 20,
    battery_voltage_v: Number(wizard.batteryVoltage) || 7.4,
  };
  if (wizard.massKg) constraints.mass_kg = Number(wizard.massKg);

  const clarifier = wizard.clarifier || null;
  const base = {
    constraints,
    export_gerber: false,
    material_mode: "scratch",
    clarifier,
  };

  if (wizard.designStrategy === "canvas" && (wizard.selectedModuleIds || []).length >= 2) {
    return {
      ...base,
      module_ids: [...wizard.selectedModuleIds],
      allow_llm_first: false,
    };
  }

  return {
    ...base,
    phrase: goal,
    allow_llm_first: wizard.designStrategy !== "heuristic",
  };
}

export function wizardIsGreenfield(wizard) {
  return wizard.mode === "greenfield";
}

export function wizardNeedsDonorStep(wizard) {
  return wizard.mode === "salvage";
}

export function getWizardSteps(wizard) {
  const steps = [
    { id: "goal", label: "Your project" },
    { id: "clarify", label: "Quick questions" },
    { id: "mode", label: "Design path" },
  ];
  if (wizard.mode === "salvage") {
    steps.push({ id: "parts", label: "Parts you have" }, { id: "donor", label: "Donor board + AI" });
  } else {
    steps.push({ id: "design", label: "Design preference" });
  }
  steps.push({ id: "power", label: wizard.mode === "salvage" ? "Power & limits" : "Constraints" });
  steps.push({ id: "review", label: "Review" });
  return steps;
}

export { PART_TYPES, INITIAL_WIZARD, defaultPart, slugify };
