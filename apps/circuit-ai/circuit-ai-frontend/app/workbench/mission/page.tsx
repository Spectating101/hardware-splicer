import { DonorIntakePanel } from '@/components/workbench/donor-intake-panel';
import { ReuseMissionOverview } from '@/components/workbench/reuse-mission-overview';

export default function ReuseMissionPage() {
  return (
    <div className="min-h-screen bg-[#040811] text-slate-100">
      <div className="mx-auto max-w-7xl px-4 pt-6 lg:px-6 lg:pt-8">
        <DonorIntakePanel />
      </div>
      <ReuseMissionOverview />
    </div>
  );
}
