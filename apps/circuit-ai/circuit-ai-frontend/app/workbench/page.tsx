import { ConstructorPlannerBridge } from '@/components/workbench/constructor-planner-bridge';
import { MachineWorkbench } from '@/components/workbench/machine-workbench';
import { SpatialCommandConsole } from '@/components/workbench/spatial-command-console';

export default function WorkbenchPage() {
  return (
    <>
      <ConstructorPlannerBridge />
      <MachineWorkbench />
      <SpatialCommandConsole />
    </>
  );
}
