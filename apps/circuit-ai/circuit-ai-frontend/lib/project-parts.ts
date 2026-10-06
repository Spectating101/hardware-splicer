'use client';

import { useCallback, useEffect, useState } from 'react';

export type ProviderRecord = {
  source: string;
  as_of?: string;
  lifecycle?: string | null;
  stock?: number | null;
  datasheet_url?: string | null;
  alternates?: { mpn: string; manufacturer?: string | null; reason?: string }[];
  package?: string | null;
};

export type BomGroup = {
  value?: string;
  footprint?: string;
  mpn?: string | null;
  lcsc?: string | null;
  manufacturer?: string | null;
  dnp?: boolean;
  quantity: number;
  refs: string[];
  flags?: { missing_mpn?: boolean; dnp?: boolean; not_in_bom?: boolean };
  datasheet?: string | null;
  availability?: { status: 'not_checked' | 'checked' | 'lookup_failed' | 'no_data'; records?: ProviderRecord[]; note?: string };
};

export type PartsResult = {
  available: boolean;
  reason?: string;
  summary?: { components: number; groups: number; unique_mpns: number; missing_mpn_groups: number; dnp_components: number; excluded_components: number };
  bom_groups: BomGroup[];
  enrichment?: { requested?: boolean; providers?: string[]; performed?: boolean; reason?: string };
};

/** Parts of a retained schematic revision. Enrichment is a separate, explicit request so nothing leaves the host unasked. */
export function useProjectParts(projectId: string, revision: number | null, active: boolean) {
  const [result, setResult] = useState<PartsResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async (enrich: boolean) => {
    if (!projectId || !revision) return;
    setLoading(true);
    setError('');
    try {
      const response = await fetch(`/api/proxy/engineering/projects/${encodeURIComponent(projectId)}/revisions/${revision}/parts?enrich=${enrich}`, { cache: 'no-store' });
      const body = await response.json();
      if (!response.ok || body?.ok === false) throw new Error(body?.error || body?.detail?.message || 'The parts list could not be loaded.');
      setResult({ available: body.available !== false, reason: body.reason, summary: body.summary, bom_groups: body.bom_groups || [], enrichment: body.enrichment });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The parts list could not be loaded.');
    } finally {
      setLoading(false);
    }
  }, [projectId, revision]);

  useEffect(() => {
    if (active) void load(false);
  }, [active, load]);

  return { result, loading, error, checkAvailability: () => load(true) };
}
