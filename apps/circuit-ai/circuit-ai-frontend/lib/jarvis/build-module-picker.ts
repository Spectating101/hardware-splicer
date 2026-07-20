import {
  findModule,
  findModulesByCapabilities,
  type ModuleSpec,
} from "@/lib/modules/module-library";
import { expandUserPhrase } from "@/lib/jarvis/phrase-expander";

export type ModulePick = {
  moduleIds: string[];
  labels: string[];
  hints: string[];
};

type ModuleHint = {
  patterns: RegExp[];
  label: string;
  requiresAny: string[][];
  preferId?: string;
  /** Higher wins when multiple hints match — avoids vague picks beating specific ones. */
  priority?: number;
};

const MODULE_HINTS: ModuleHint[] = [
  {
    patterns: [/ds18b20|one.?wire temp|digital temp probe/],
    label: "1-wire temperature",
    requiresAny: [["sensor_or_adc"]],
    preferId: "ds18b20",
    priority: 10,
  },
  {
    patterns: [/pressure|barometric|altitude|bme280|bmp280|environmental sensor/],
    label: "pressure/environment sensing",
    requiresAny: [["sensor_or_adc"]],
    preferId: "bme280",
    priority: 9,
  },
  {
    patterns: [/temp|humidity|thermostat|climate|hot|cold|weather/],
    label: "temperature/humidity sensing",
    requiresAny: [["sensor_or_adc"]],
    preferId: "dht22",
    priority: 5,
  },
  {
    patterns: [/soil|moist|wet plant|dry plant|garden/],
    label: "soil moisture",
    requiresAny: [["sensor_or_adc"]],
    preferId: "soil_moisture",
    priority: 8,
  },
  {
    patterns: [/distance|ultrasonic|how far|proximity|object near/],
    label: "distance sensing",
    requiresAny: [["sensor_or_adc"]],
    preferId: "hc-sr04",
    priority: 8,
  },
  {
    patterns: [/light level|brightness|dark|ldr|photoresistor/],
    label: "light sensing",
    requiresAny: [["sensor_or_adc"]],
    preferId: "ldr_photoresistor",
    priority: 7,
  },
  {
    patterns: [/co2|air quality|voc|gas sensor|smoke detect/],
    label: "air quality",
    requiresAny: [["sensor_or_adc"]],
    preferId: "mq-2_gas_sensor",
    priority: 8,
  },
  {
    patterns: [/solenoid|valve|garage door|dry contact/],
    label: "solenoid/valve control",
    requiresAny: [["actuator_driver"]],
    preferId: "relay-1ch-5v",
    priority: 8,
  },
  {
    patterns: [/relay|switch (?:a |the )?(?:lamp|light|outlet|heater)|turn (?:on|off)/],
    label: "relay switching",
    requiresAny: [["actuator_driver"]],
    preferId: "relay-1ch-5v",
    priority: 7,
  },
  {
    patterns: [/mosfet|high.?current switch|pump driver/],
    label: "load driver",
    requiresAny: [["actuator_driver"]],
    preferId: "mosfet-irlz44n",
    priority: 6,
  },
  {
    patterns: [/servo|rc servo/],
    label: "servo motion",
    requiresAny: [["motor_or_load", "mechanical_motion"]],
    preferId: "sg90",
    priority: 7,
  },
  {
    patterns: [/stepper|cnc|plotter|pen plot/],
    label: "stepper motion",
    requiresAny: [["mechanical_motion", "actuator_driver"]],
    preferId: "a4988-stepper",
    priority: 8,
  },
  {
    patterns: [/dc motor|wheel|spin(?:ning)?|tank tread/],
    label: "motor drive",
    requiresAny: [["motor_or_load", "actuator_driver"]],
    preferId: "l298n",
    priority: 7,
  },
  {
    patterns: [/pump|water flow|move water/],
    label: "pump",
    requiresAny: [["fan_or_pump", "motor_or_load"]],
    preferId: "water_pump_5v",
    priority: 8,
  },
  {
    patterns: [/fan|blow air|cool(?:ing)?/],
    label: "fan",
    requiresAny: [["fan_or_pump", "motor_or_load"]],
    preferId: "cooling_fan_5v",
    priority: 7,
  },
  {
    patterns: [/display|screen|oled|show (?:text|numbers)|show sensor|readings on (?:a )?screen/i],
    label: "display",
    requiresAny: [["display_or_ui"]],
    preferId: "ssd1306-128x64",
    priority: 6,
  },
  {
    patterns: [/room monitor|weather station|environment(?:al)? (?:station|panel)|multi.?sensor/i],
    label: "room monitor",
    requiresAny: [["sensor_or_adc"], ["display_or_ui"]],
    preferId: "bme280",
    priority: 9,
  },
  {
    patterns: [/camera|take photos?|video|webcam|watch/],
    label: "camera",
    requiresAny: [["camera_or_vision"]],
    preferId: "esp32-cam-module",
    priority: 8,
  },
  {
    patterns: [/speaker|audio|beep|sound|play a tone/],
    label: "audio output",
    requiresAny: [["speaker_or_audio"]],
    preferId: "max98357a-i2s-amp",
    priority: 7,
  },
  {
    patterns: [/button|keypad|\bpress(?:able)?\b|macro pad/],
    label: "buttons",
    requiresAny: [["switch_or_button"]],
    preferId: "capacitive_touch",
    priority: 5,
  },
  {
    patterns: [/led|indicator light|status light|blink/],
    label: "indicator LED",
    requiresAny: [["led_or_light", "display_or_ui"]],
    priority: 5,
  },
  {
    patterns: [/wifi|wireless|internet|bluetooth|esp-?now|home assistant|esphome/],
    label: "wireless",
    requiresAny: [["wireless"]],
    preferId: "esp32-devkit",
    priority: 4,
  },
  {
    patterns: [/tft|touchscreen|ili9341|lvgl|cheap yellow display|cyd/],
    label: "touch display",
    requiresAny: [["display_or_ui"]],
    preferId: "ili9341_tft",
    priority: 8,
  },
  {
    patterns: [/12v|barrel|wall wart|bench supply/],
    label: "higher-voltage input",
    requiresAny: [["power"]],
    preferId: "dc-barrel-12v",
    priority: 6,
  },
  {
    patterns: [/buck|step down|regulate(?:d)? power/],
    label: "buck regulator",
    requiresAny: [["power"]],
    preferId: "buck-lm2596",
    priority: 6,
  },
];

const SENSOR_PREFER_IDS = new Set([
  "dht22", "ds18b20", "bme280", "soil_moisture", "hc-sr04", "ldr_photoresistor",
  "mq-2_gas_sensor",
]);

function normalizeUserText(text: string): string {
  return text
    .toLowerCase()
    .replace(/[''`]/g, "'")
    .replace(/[""]/g, '"');
}

function hintMatchScore(hint: ModuleHint, text: string): number {
  let best = 0;
  for (const pattern of hint.patterns) {
    const m = text.match(pattern);
    if (m) best = Math.max(best, m[0].length + (hint.priority ?? 0));
  }
  return best;
}

function pickFromCapabilities(group: string[], exclude: Set<string>, preferId?: string): ModuleSpec | undefined {
  if (preferId && !exclude.has(preferId)) {
    const pref = findModule(preferId);
    if (pref) return pref;
  }
  const candidates = findModulesByCapabilities([group])
    .filter((m) => !exclude.has(m.id))
    .sort((a, b) => (a.capabilityTags?.length ?? 99) - (b.capabilityTags?.length ?? 99));
  return candidates[0];
}

function filterRedundantHints(
  ranked: Array<{ hint: ModuleHint; score: number }>,
  text: string,
): ModuleHint[] {
  const picked = ranked.map((r) => r.hint);
  const has = (preferId: string) => picked.some((h) => h.preferId === preferId);

  return picked.filter((hint) => {
    if (hint.preferId === "dht22" && has("ds18b20")) return false;
    if (hint.preferId === "dht22" && has("bme280") && /pressure|barometric|environmental|bme|bmp/.test(text)) {
      return false;
    }
    if (hint.label === "wireless" && picked.length > 1) return false;
    return true;
  });
}

/** Pick concrete library modules from normie functional language. */
export function pickModulesForGoal(text: string): ModulePick {
  const t = normalizeUserText(expandUserPhrase(text));
  const ranked = MODULE_HINTS
    .map((hint) => ({ hint, score: hintMatchScore(hint, t) }))
    .filter((entry) => entry.score > 0)
    .sort((a, b) => b.score - a.score);

  const matchedHints = filterRedundantHints(ranked, t);
  if (matchedHints.length === 0) {
    return { moduleIds: [], labels: [], hints: [] };
  }

  const moduleIds = new Set<string>();
  const labels: string[] = [];
  const hints: string[] = matchedHints.map((h) => h.label);

  const soloPart = /(?:^|\b)(?:just|only)\s+(?:a|an)\s+/.test(t) && matchedHints.length === 1;
  const needsBrain = !soloPart && !/no (?:mcu|microcontroller|brain|controller)/.test(t);
  const needsUsbPower = needsBrain && !/battery|lipo|li.?ion/.test(t);

  if (needsUsbPower) {
    moduleIds.add("usb-power-5v");
    labels.push(findModule("usb-power-5v")?.label ?? "USB 5V power");
  }
  if (needsBrain) {
    moduleIds.add("esp32-devkit");
    labels.push(findModule("esp32-devkit")?.label ?? "ESP32 DevKit");
  }

  const sensorPicks = new Set<string>();
  for (const hint of matchedHints) {
    for (const group of hint.requiresAny) {
      const pick = pickFromCapabilities(group, moduleIds, hint.preferId);
      if (!pick) continue;
      if (SENSOR_PREFER_IDS.has(pick.id) && sensorPicks.has(pick.id)) continue;
      if (SENSOR_PREFER_IDS.has(pick.id)) sensorPicks.add(pick.id);
      moduleIds.add(pick.id);
      labels.push(pick.label);
    }
  }

  if (needsBrain && /pump|motor|relay|servo|stepper|fan/.test(t)) {
    if (/pump|fan/.test(t) && !moduleIds.has("mosfet-irlz44n")) {
      moduleIds.add("mosfet-irlz44n");
      labels.push(findModule("mosfet-irlz44n")?.label ?? "MOSFET driver");
    }
    if (/stepper|12v|barrel/.test(t) && !moduleIds.has("buck-lm2596")) {
      moduleIds.add("buck-lm2596");
      labels.push(findModule("buck-lm2596")?.label ?? "Buck regulator");
    }
  }

  const fiveVSignalIds = new Set(["hc-sr04"]);
  const needsLevelShift = needsBrain && [...moduleIds].some((id) => fiveVSignalIds.has(id));
  if (needsLevelShift && !moduleIds.has("level-shifter-4ch")) {
    moduleIds.add("level-shifter-4ch");
    labels.push(findModule("level-shifter-4ch")?.label ?? "Level shifter");
  }

  return {
    moduleIds: [...moduleIds],
    labels: [...new Set(labels)],
    hints,
  };
}

export function wantsModuleComposition(text: string): boolean {
  const t = normalizeUserText(text);
  if (pickModulesForGoal(text).moduleIds.length === 0) return false;
  if (/(?:^|\b)(?:add|include|need|want|with (?:a|an)|on (?:a |the )?(?:small )?screen|something that|that (?:measures|reads|senses|controls|drives|spins|monitors)|uses? (?:a|an))/.test(t)) {
    return true;
  }
  if (/(?:build|make|create|set up|help me)/.test(t)) return true;
  return false;
}
