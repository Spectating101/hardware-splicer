// Thin localStorage-backed inventory store. Photos live in IndexedDB in v2;
// v1 keeps the blob URL or a data-URL in the same JSON payload for simplicity.

import type { InventoryPart } from "@/lib/cad-types";

const KEY = "circuit.inventory.v1";

export function loadInventory(): InventoryPart[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return [];
    return JSON.parse(raw) as InventoryPart[];
  } catch {
    return [];
  }
}

export function saveInventory(items: InventoryPart[]) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(KEY, JSON.stringify(items));
  } catch {
    // quota exceeded — silent, UI shows current state regardless
  }
}

export function clearInventory() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(KEY);
}
