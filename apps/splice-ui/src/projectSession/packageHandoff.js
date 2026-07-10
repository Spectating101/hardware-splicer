/**
 * Package handoff for async job bundles vs synchronous Studio builds.
 * Prefer deriving from session; reducer may also store a snapshot.
 */

import { jobBundleUrl, buildPackageArchiveUrl } from "../api.js";

function hasPackage(session) {
  return Boolean(session?.projectPackage);
}

/**
 * @returns {{
 *   kind: "job_bundle" | "build_package" | "local_only",
 *   url: string | null,
 *   available: boolean,
 *   explanation: string
 * }}
 */
export function derivePackageHandoff(session = {}) {
  if (session.packageHandoff && typeof session.packageHandoff === "object") {
    const snap = session.packageHandoff;
    if (snap.kind && snap.available != null) {
      if (snap.kind === "job_bundle" && session.activeJobId) {
        return {
          kind: "job_bundle",
          url: jobBundleUrl(session.activeJobId),
          available: true,
          explanation: snap.explanation || "Download the async job artifact zip.",
        };
      }
      if (snap.kind === "build_package" && (session.buildDir || session.projectPackage?.build_dir)) {
        const dir = session.buildDir || session.projectPackage.build_dir;
        return {
          kind: "build_package",
          url: buildPackageArchiveUrl(dir),
          available: true,
          explanation:
            snap.explanation || "Download the project package archive from this Studio build.",
        };
      }
      if (snap.kind === "local_only") {
        return {
          kind: "local_only",
          url: null,
          available: false,
          explanation:
            snap.explanation ||
            "Package is present in this session but no downloadable archive URL is available.",
        };
      }
    }
  }

  if (session.activeJobId) {
    return {
      kind: "job_bundle",
      url: jobBundleUrl(session.activeJobId),
      available: true,
      explanation: "Download the async job artifact zip.",
    };
  }

  const buildDir = session.buildDir || session.projectPackage?.build_dir || null;
  if (hasPackage(session) && buildDir) {
    return {
      kind: "build_package",
      url: buildPackageArchiveUrl(buildDir),
      available: true,
      explanation: "Download the project package archive from this Studio build.",
    };
  }

  if (hasPackage(session)) {
    return {
      kind: "local_only",
      url: null,
      available: false,
      explanation:
        "Package artifacts are in this in-memory session, but no build directory is available to archive.",
    };
  }

  return {
    kind: "local_only",
    url: null,
    available: false,
    explanation: "Generate a project package from Design or a salvage build first.",
  };
}

export function packageHandoffSnapshot(partial = {}) {
  return derivePackageHandoff({ ...partial, packageHandoff: null });
}
