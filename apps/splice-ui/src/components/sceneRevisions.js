// Revisions with both a GLB and a parts sidecar can be drawn; the rest stay records only.
export function sceneRevisions(manifest) {
  return (manifest?.revisions ?? []).filter((row) => row.glb && row.parts).map((row) => [row.id, row.label || row.id]);
}
