// Adapts catalog recipes to salvage inventory: power topology + owned modules.

import type { SalvagePlanInput } from "./plan-to-graph";

type Wire = { from: { role: string; pin: string }; to: { role: string; pin: string } };
export type Recipe = {
  modules: Array<{ role: string; moduleId: string }>;
  wires: Wire[];
  notes?: string[];
};

const BUCK_ROLES = new Set(["buck", "psu", "mot_psu"]);
const BARREL_ID = "dc-barrel-12v";
const USB_ID = "usb-power-5v";

function hasRole(modules: Recipe["modules"], role: string): boolean {
  return modules.some((m) => m.role === role);
}

function moduleIdFor(modules: Recipe["modules"], role: string): string | undefined {
  return modules.find((m) => m.role === role)?.moduleId;
}

function dropRoles(modules: Recipe["modules"], roles: Set<string>): Recipe["modules"] {
  return modules.filter((m) => !roles.has(m.role));
}

function dropWiresTouchingRoles(wires: Wire[], roles: Set<string>): Wire[] {
  return wires.filter((w) => !roles.has(w.from.role) && !roles.has(w.to.role));
}

/** Barrel + buck/psu + driver (bench loads without a separate USB MCU rail). */
function usbBenchLoadTopology(recipe: Recipe): Recipe | null {
  if (moduleIdFor(recipe.modules, "pwr") !== BARREL_ID) return null;
  if (hasRole(recipe.modules, "mcu") || hasRole(recipe.modules, "usb")) return null;
  const buckRole = recipe.modules.find((m) => BUCK_ROLES.has(m.role))?.role;
  if (!buckRole || !hasRole(recipe.modules, "drv")) return null;

  const drop = new Set(["pwr", buckRole]);
  const modules = [{ role: "pwr", moduleId: USB_ID }, ...dropRoles(recipe.modules, drop)];
  const wires = [
    { from: { role: "pwr", pin: "V+" }, to: { role: "drv", pin: "VIN" } },
    { from: { role: "pwr", pin: "GND" }, to: { role: "drv", pin: "VIN-" } },
    { from: { role: "pwr", pin: "GND" }, to: { role: "drv", pin: "GND" } },
  ];
  return {
    modules,
    wires,
    notes: [...(recipe.notes || []), "Inventory: USB 5V salvage path — barrel and buck omitted."],
  };
}

/** Dual-rail USB MCU + barrel servo/motor PSU — USB-only inventory. */
function usbDropHighVoltageRail(recipe: Recipe): Recipe | null {
  if (moduleIdFor(recipe.modules, "pwr") !== BARREL_ID) return null;
  if (!hasRole(recipe.modules, "usb")) return null;

  const hvRoles = new Set(["pwr", "svo_psu", "mot_psu"]);
  let modules = dropRoles(recipe.modules, hvRoles);
  const wires = dropWiresTouchingRoles(recipe.wires, hvRoles);

  // Feed servo from USB 5V when present
  const extra: Wire[] = [];
  if (hasRole(modules, "svo")) {
    extra.push(
      { from: { role: "usb", pin: "V+" }, to: { role: "svo", pin: "VCC" } },
      { from: { role: "usb", pin: "GND" }, to: { role: "svo", pin: "GND" } },
    );
    const sig = recipe.wires.find((w) => w.to.role === "svo" && w.to.pin === "SIG");
    if (sig) extra.push(sig);
  }

  return {
    modules,
    wires: [...wires, ...extra],
    notes: [...(recipe.notes || []), "Inventory: USB-only — 12V barrel and HV PSU omitted."],
  };
}

/** Robot: barrel motor buck + USB MCU → USB-only drops motor buck, keeps USB MCU path. */
function usbRobotTopology(recipe: Recipe): Recipe | null {
  if (moduleIdFor(recipe.modules, "pwr") !== BARREL_ID) return null;
  if (!hasRole(recipe.modules, "mot_psu") || !hasRole(recipe.modules, "usb")) return null;

  const drop = new Set(["pwr", "mot_psu"]);
  const modules = dropRoles(recipe.modules, drop);
  const wires = dropWiresTouchingRoles(recipe.wires, drop);
  // Motor driver fed from USB 5V (bench-limited; note in output)
  const extra: Wire[] = [
    { from: { role: "usb", pin: "V+" }, to: { role: "drv", pin: "VCC" } },
    { from: { role: "usb", pin: "GND" }, to: { role: "drv", pin: "GND" } },
  ];
  const ctrl = recipe.wires.filter(
    (w) => w.from.role === "mcu" && w.to.role === "drv",
  );
  return {
    modules,
    wires: [...wires, ...extra, ...ctrl],
    notes: [
      ...(recipe.notes || []),
      "Inventory: USB-only — motor buck omitted; driver on 5V USB (small motors only).",
    ],
  };
}

function pruneToInventory(recipe: Recipe, plan: SalvagePlanInput): Recipe {
  if (plan.strategy_mode !== "constrained") return recipe;
  const resolved = plan.resolved_modules || [];
  const ownedIds = new Set(
    resolved
      .filter((r) => r.module_id && r.source !== "unresolved")
      .map((r) => String(r.module_id)),
  );
  if (ownedIds.size < 2) return recipe;

  const modules = recipe.modules.filter((m) => ownedIds.has(m.moduleId));
  if (modules.length < 2 || modules.length === recipe.modules.length) return recipe;

  const keptRoles = new Set(modules.map((m) => m.role));
  const wires = recipe.wires.filter(
    (w) => keptRoles.has(w.from.role) && keptRoles.has(w.to.role),
  );
  return {
    modules,
    wires,
    notes: [
      ...(recipe.notes || []),
      `Inventory prune: ${modules.length}/${recipe.modules.length} modules from owned parts.`,
    ],
  };
}

function applyModuleOverrides(recipe: Recipe, overrides: Record<string, string>): Recipe {
  if (!Object.keys(overrides).length) return recipe;
  return {
    ...recipe,
    modules: recipe.modules.map((m) => ({
      ...m,
      moduleId: overrides[m.role] || m.moduleId,
    })),
  };
}

export function adaptRecipeToInventory(
  recipe: Recipe,
  plan: SalvagePlanInput,
): { recipe: Recipe; notes: string[] } {
  const notes: string[] = [];
  const overrides = { ...(plan.module_overrides || {}) };

  // Topology transforms inspect catalog roles (barrel + buck) — run before overrides.
  let adapted: Recipe = {
    modules: recipe.modules.map((m) => ({ ...m })),
    wires: [...recipe.wires],
    notes: recipe.notes ? [...recipe.notes] : [],
  };

  if (plan.power_topology === "usb_5v") {
    for (const fn of [usbRobotTopology, usbDropHighVoltageRail, usbBenchLoadTopology]) {
      const next = fn(adapted);
      if (next) {
        adapted = next;
        notes.push("Applied USB 5V inventory power topology.");
        break;
      }
    }
  }

  adapted = applyModuleOverrides(adapted, overrides);
  adapted = pruneToInventory(adapted, plan);

  return { recipe: adapted, notes };
}
