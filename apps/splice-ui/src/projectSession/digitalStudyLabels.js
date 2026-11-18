export function fieldLabel(key) {
  const units = { a: "A", h: "h", mm: "mm", g: "g", w: "W", v: "V", s: "s", mah: "mAh" };
  const words = key.split("_");
  const unit = units[words.at(-1)];
  if (unit) words.pop();
  const name = words.join(" ");
  return name.charAt(0).toUpperCase() + name.slice(1) + (unit ? ` (${unit})` : "");
}
