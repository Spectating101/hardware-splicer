/** Top-level UI views — single source for App + tests. */

export const VIEWS = Object.freeze({
  home: "home",
  workspace: "workspace",
  advanced: "advanced",
  example: "example",
  lab: "lab",
  preview: "preview",
});

export const ADVANCED_VIEWS = new Set([
  VIEWS.advanced,
  VIEWS.example,
  VIEWS.lab,
  VIEWS.preview,
]);

export function isAdvancedView(view) {
  return ADVANCED_VIEWS.has(view);
}
