import { ConstructorPlannerBridge } from '@/components/workbench/constructor-planner-bridge';
import { MachineWorkbench } from '@/components/workbench/machine-workbench';
import { SpatialCommandConsole } from '@/components/workbench/spatial-command-console';
import { WorkbenchProjectBridge } from '@/components/workbench/workbench-project-bridge';

export default function WorkbenchPage() {
  return (
    <>
      <WorkbenchProjectBridge />
      <ConstructorPlannerBridge />
      <MachineWorkbench />
      <SpatialCommandConsole />
    </>
  );
}
