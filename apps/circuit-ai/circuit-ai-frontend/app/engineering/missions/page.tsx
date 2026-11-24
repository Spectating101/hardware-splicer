'use client';

import { Suspense, useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { BuildSheetPanel } from '@/components/engineering/mission-build-sheet';
import { fetchMission, type Mission } from '@/lib/missions';

/**
 * Read-only view of one fabrication mission: /engineering/missions?project=<id>&mission=<id>.
 * It only reads. Opening, accepting, answering, running, staging or building a mission is not offered here.
 */
function MissionReview() {
  const params = useSearchParams();
  const project = params.get('project') || '';
  const missionId = params.get('mission') || '';
  const [mission, setMission] = useState<Mission | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!project || !missionId) return;
    let live = true;
    setMission(null);
    setError('');
    fetchMission(project, missionId)
      .then((result) => { if (live) setMission(result); })
      .catch((caught: unknown) => {
        if (live) setError(caught instanceof Error ? caught.message : 'Could not load the mission');
      });
    return () => { live = false; };
  }, [project, missionId]);

  return (
    <main className="mx-auto max-w-4xl space-y-4 px-4 py-8">
      <h1 className="text-lg font-semibold text-slate-100">Mission review</h1>
      <p className="text-xs leading-5 text-slate-400">
        A read-only look at what an agent proposed and what Hardware Splicer recorded. Nothing on this page can
        change a mission or authorize construction, flashing or power-on.
      </p>
      {!project || !missionId ? (
        <p data-testid="mission-review-missing" className="text-sm text-slate-300">
          Open this page with ?project=&lt;project id&gt;&amp;mission=&lt;mission id&gt;.
        </p>
      ) : null}
      {error ? <p role="alert" className="text-sm text-red-200">{error}</p> : null}
      {mission && !mission.accepted ? (
        <p data-testid="mission-review-unaccepted" className="text-sm text-slate-300">
          This mission has not been accepted by a person, so there is no review sheet yet.
        </p>
      ) : null}
      {mission ? <BuildSheetPanel mission={mission} /> : null}
    </main>
  );
}

export default function MissionsPage() {
  return (
    <Suspense fallback={null}>
      <MissionReview />
    </Suspense>
  );
}
