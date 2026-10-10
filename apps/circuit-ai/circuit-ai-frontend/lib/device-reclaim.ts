import { getProxyErrorMessage, isProxyFailure, readJsonPayload } from '@/lib/proxy-client';

export const RECLAIM_DEVICE_STORAGE = 'hs-device-reclaim-v1';
export type ReclaimInput = { ref: string; kind: string; marking: string };
export type DeviceReclaimMatch = { module: string; name: string; tier: 'exact' | 'variant'; matched_name: string } & (
  | { relation: 'module'; matched_field: 'name' | 'mpn' }
  | { relation: 'chip_on_module'; matched_field: 'chips.marking'; role: string; source: string; note: string }
);
export type DeviceReclaimRow = ReclaimInput & {
  matched: boolean;
  matches: DeviceReclaimMatch[];
};
export type DeviceReclaimResult = { parts: DeviceReclaimRow[]; note: string };

/** Only typed markings and reported kinds travel; library identities and readings do not. */
export async function fetchDeviceReclaimMatches(body: unknown, signal?: AbortSignal): Promise<DeviceReclaimResult> {
  const response = await fetch('/api/proxy/engineering/devices/reclaim-matches', {
    method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body), cache: 'no-store', signal,
  });
  const result = await readJsonPayload<unknown>(response);
  if (!response.ok || !result || isProxyFailure(result)) throw new Error(getProxyErrorMessage(result, 'The device library matches could not be checked.'));
  return result as DeviceReclaimResult;
}
