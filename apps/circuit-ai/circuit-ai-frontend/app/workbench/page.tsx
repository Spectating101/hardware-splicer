import { ConstructorPlannerBridge } from '@/components/workbench/constructor-planner-bridge';
import { MachineWorkbench } from '@/components/workbench/machine-workbench';
import { SpatialCommandConsole } from '@/components/workbench/spatial-command-console';
import { WorkbenchAnchorIntentRehydrator } from '@/components/workbench/workbench-anchor-intent-rehydrator';
import { WorkbenchDonorEvidencePanel } from '@/components/workbench/workbench-donor-evidence-panel';
import { WorkbenchDonorSessionBadge } from '@/components/workbench/workbench-donor-session-badge';
import { WorkbenchProjectBridge } from '@/components/workbench/workbench-project-bridge';
import { WorkbenchStageBridge } from '@/components/workbench/workbench-stage-bridge';

export default function WorkbenchPage() {
  return (
    <>
      <WorkbenchProjectBridge />
      <WorkbenchAnchorIntentRehydrator />
      <ConstructorPlannerBridge />
      <WorkbenchStageBridge />
      <WorkbenchDonorSessionBadge />
      <WorkbenchDonorEvidencePanel />
      <MachineWorkbench />
      <SpatialCommandConsole />
    </>
  );
}
