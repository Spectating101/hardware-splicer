// How a check's result moved between two revisions, said from the data rather than the backend's
// one-word transition. A result that flipped because the limit moved, with the measured value
// unchanged, is a changed requirement, not a regression of the design.

export type DerivedTransitionKind =
  | "newly-fails-requirement"
  | "regressed"
  | "newly-fails"
  | "newly-passes-requirement"
  | "improved"
  | "newly-passes"
  | "unchanged"
  | "changed";

export type TransitionKind = DerivedTransitionKind | "unknown";

export type InvalidationReasonKind =
  | "changed_dependency"
  | "rerun_result_differs"
  | "check_absent_in_candidate";

export type CheckValue = number | string | boolean | null | undefined;

export interface CheckResultInput {
  passed?: boolean | null;
  actual?: CheckValue;
  limit?: CheckValue;
  unit?: string | null;
}

export interface TransitionDescription<K extends string = TransitionKind> {
  kind: K;
  label: string;
  detail: string;
}

export interface InvalidationReasonInput {
  kind?: InvalidationReasonKind;
  ids?: readonly string[] | null;
}

const EPSILON = 1e-9;
const same = (a: CheckValue, b: CheckValue): boolean => typeof a === "number" && typeof b === "number" ? Math.abs(a - b) <= EPSILON * Math.max(1, Math.abs(a)) : a === b;
const fmt = (value: CheckValue, unit: string): string => value === undefined || value === null ? "unknown" : `${value}${unit ? ` ${unit}` : ""}`;

/**
 * @param before check result in the earlier revision ({ passed, actual, limit, unit }) or null
 * @param after check result in the later revision, or null
 * @param fallback the backend's transition word, used only when the data cannot say more
 * @returns {{ kind: string, label: string, detail: string }}
 */
export function describeTransition<F extends string = "unknown">(
  before: CheckResultInput | null | undefined,
  after: CheckResultInput | null | undefined,
  fallback: F = "unknown" as F,
): TransitionDescription<DerivedTransitionKind | F> {
  if (!before || !after) {
    return { kind: fallback, label: !after ? "Not run in the later revision" : !before ? "Not run in the earlier revision" : fallback, detail: "" };
  }
  const unit = after.unit || before.unit || "";
  const actualSame = same(before.actual, after.actual);
  const limitSame = same(before.limit, after.limit);
  const measured = actualSame
    ? `Measured ${fmt(after.actual, unit)}, unchanged`
    : `Measured ${fmt(after.actual, unit)}, was ${fmt(before.actual, unit)}`;
  const limitMoved = typeof before.limit === "number" && typeof after.limit === "number" && !limitSame
    ? (after.limit > before.limit ? "up" : "down") : null;
  const target = limitSame ? `target ${fmt(after.limit, unit)}, unchanged`
    : limitMoved ? `target ${fmt(after.limit, unit)}, ${limitMoved} from ${fmt(before.limit, unit)}`
      : `target ${fmt(after.limit, unit)}, was ${fmt(before.limit, unit)}`;
  const detail = `${measured} · ${target}`;
  const requirement = limitMoved === "up" ? "requirement increased" : limitMoved === "down" ? "requirement lowered" : "requirement changed";

  if (before.passed === true && after.passed === false) {
    if (actualSame && !limitSame) return { kind: "newly-fails-requirement", label: `Newly fails: ${requirement}`, detail };
    if (!actualSame && limitSame) return { kind: "regressed", label: "Regressed: measured value worsened", detail };
    if (!actualSame && !limitSame) return { kind: "newly-fails", label: `Newly fails: measured value and ${requirement}`, detail };
    return { kind: "newly-fails", label: "Newly fails", detail };
  }
  if (before.passed === false && after.passed === true) {
    if (actualSame && !limitSame) return { kind: "newly-passes-requirement", label: `Newly passes: ${requirement}`, detail };
    if (!actualSame && limitSame) return { kind: "improved", label: "Newly passes: measured value improved", detail };
    return { kind: "newly-passes", label: "Newly passes", detail };
  }
  if (before.passed === after.passed) {
    const state = after.passed === true ? "passes" : after.passed === false ? "fails" : "unknown";
    return { kind: actualSame && limitSame ? "unchanged" : "changed", label: actualSame && limitSame
      ? `Unchanged · ${state === "unknown" ? "result unknown" : `${state} in both`}` : `Still ${state === "unknown" ? "unknown" : state}`, detail };
  }
  return { kind: fallback, label: fallback, detail };
}

/** Why the backend invalidated a revision's evidence, in words. */
export function invalidationReason(reasons: readonly InvalidationReasonInput[] = []): string {
  const parts = reasons.flatMap((reason) => {
    if (reason.kind === "changed_dependency") {
      const ids = reason.ids || [];
      return ids.some((id) => id.startsWith("requirement:")) ? ["changed requirement"] : ["changed input"];
    }
    if (reason.kind === "rerun_result_differs") return ["rerun result differs"];
    if (reason.kind === "check_absent_in_candidate") return ["check absent from the new revision"];
    return [];
  });
  return [...new Set(parts)].join(", ") || "reason not given";
}
