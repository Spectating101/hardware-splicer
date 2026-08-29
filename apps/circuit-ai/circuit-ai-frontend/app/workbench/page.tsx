import { MachineWorkbench } from '@/components/workbench/machine-workbench';
import { SpatialCommandConsole } from '@/components/workbench/spatial-command-console';

export default function WorkbenchPage() {
  return (
    <>
      <MachineWorkbench />
      <SpatialCommandConsole />
    </>
  );
}