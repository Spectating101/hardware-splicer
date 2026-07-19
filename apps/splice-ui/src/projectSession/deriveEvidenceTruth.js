/**
 * Evidence authority view model for salvage projects.
 *
 * Source precedence:
 * 1. refreshed Bench session evidence integrations
 * 2. result.salvage_package.evidence_integrations
 * 3. result.evidence_integrations
 * 4. package.evidence_integrations
 * 5. conservative legacy fallback from donor-bound resolved modules
 */

function pickEvidenceIntegrations(session = {}) {
  const result = session.displayResult || {};
  const salvage = result.salvage_package || session.composeResult?.salvage_package || {};
  return (
    session.benchSession?.evidence_integrations ||
    salvage.evidence_integrations ||
    result.evidence_integrations ||
    session.projectPackage?.evidence_integrations ||
    session.intake?.evidence_integrations ||
    null
  );
}

function legacyInterfaces(session = {}) {
  const result = session.displayResult || {};
  const salvage = result.salvage_package || session.composeResult?.salvage_package || {};
  return (salvage.resolved_modules || [])
    .filter((row) => String(row?.source || "").includes("donor"))
    .map((row, index) => ({
      schema_version: "hardware_splicer.integration_stack.legacy_fallback.v1",
      interface_contract: {
        interface_id: `legacy:${row.board_id || "donor"}:${row.donor_block_id || index + 1}`,
        virtual_module_id: row.module_id || `donor:${row.board_id || "board"}:${row.donor_block_id || index + 1}`,
        board_id: row.board_id || "donor-board",
        block_id: row.donor_block_id || row.instance_id || `block-${index + 1}`,
        functional_role: row.role || "unknown",
        status: row.interface_status || "unknown",
        contacts: (row.connector_refs || []).map((ref) => ({
          contact_id: `${ref}.unknown`,
          connector_ref: ref,
          label: ref,
        })),
        signals: [],
        reference_equivalents: row.reference_equivalents || [],
        unresolved_fields: ["signals", "electrical_interface_contract"],
        firmware_authorized: false,
      },
      resolved_module: row,
      compile_status: "blocked",
      blockers: ["signals", "electrical_interface_contract"],
      bench_recipe: null,
      legacy_fallback: true,
    }));
}

function normalizedInterfaces(integrations, session) {
  if (integrations?.interfaces?.length) return integrations.interfaces;
  return legacyInterfaces(session);
}

function unique(values) {
  return [...new Set(values.filter(Boolean))];
}

export function deriveEvidenceTruth(session = {}) {
  const integrations = pickEvidenceIntegrations(session);
  const interfaces = normalizedInterfaces(integrations, session);
  const authority = integrations?.authority || {};
  const applicable = session.mode === "salvage" || Boolean(interfaces.length) || Boolean(integrations);
  const unresolved = unique(
    interfaces.flatMap((item) => item?.blockers || item?.interface_contract?.unresolved_fields || []),
  );
  const unresolvedInterfaces = interfaces.filter(
    (item) =>
      item?.compile_status !== "ready" ||
      item?.interface_contract?.firmware_authorized !== true ||
      (item?.blockers || []).length > 0,
  );
  const firmwareAuthorized = Boolean(
    authority.firmware_authorized === true && unresolvedInterfaces.length === 0,
  );
  const powerAuthorized = Boolean(
    authority.power_authorized === true || session.benchSession?.power_on_authorized === true,
  );

  let state = "not_applicable";
  let label = "Evidence not required";
  let detail = "Greenfield designs use design and bench evidence without a donor interface contract.";
  if (applicable) {
    if (!interfaces.length) {
      state = "missing";
      label = "Evidence model missing";
      detail = "The salvage result does not contain donor interface contracts yet.";
    } else if (powerAuthorized && firmwareAuthorized) {
      state = "verified";
      label = "Donor interface verified";
      detail = "Firmware and power claims are authorized by accepted interface evidence.";
    } else if (firmwareAuthorized) {
      state = "bench_required";
      label = "Interface verified · bench pending";
      detail = "Firmware bindings are authorized, but physical power-on remains blocked.";
    } else if (unresolvedInterfaces.length) {
      state = "blocked";
      label = `${unresolvedInterfaces.length} donor interface${unresolvedInterfaces.length === 1 ? "" : "s"} blocked`;
      detail = "Functional analogies are preserved, but electrical semantics are not inherited.";
    } else {
      state = "partial";
      label = "Evidence review required";
      detail = "Review donor contacts, signals, and measurement provenance before generation.";
    }
  }

  return {
    applicable,
    state,
    label,
    detail,
    authority,
    integrations,
    interfaces,
    interfaceCount: interfaces.length,
    unresolvedInterfaces,
    unresolvedFields: unresolved,
    unresolvedFieldCount: unresolved.length,
    firmwareAuthorized,
    powerAuthorized,
    claimBoundary:
      authority.claim_boundary ||
      "No downstream artifact may claim more certainty than the accepted donor evidence supports.",
    backendReadiness: {
      tscircuit: {
        state: interfaces.length ? "ready" : "waiting",
        detail: interfaces.length
          ? "Evidence-bearing circuit projection can be generated."
          : "Waiting for a donor interface model.",
      },
      platformio: {
        state: firmwareAuthorized ? "ready" : "blocked",
        detail: firmwareAuthorized
          ? "Firmware project generation is authorized."
          : "Blocked until control signals and controller pins are verified.",
      },
      kibot: {
        state: session.buildDir || session.projectPackage ? "ready" : "waiting",
        detail:
          session.buildDir || session.projectPackage
            ? "Manufacturing export can run after design review."
            : "Waiting for a compiled KiCad design.",
      },
    },
  };
}

export function evidenceTone(state) {
  if (state === "verified") return "ok";
  if (state === "blocked" || state === "missing") return "fail";
  if (state === "bench_required" || state === "partial") return "warn";
  return "neutral";
}
