export type ExecutionToolCapability = {
  operation: string;
  adapter_available: boolean;
  tool?: string | null;
  tool_path?: string | null;
  tool_installed: boolean;
  executable_under_host_policy: boolean;
  preview_available: boolean;
  physical_operation: boolean;
  limitations?: string[];
};

export type EngineeringExecutionCapability = {
  schema_version?: string;
  execution_root: string;
  execution_enabled: boolean;
  operations: ExecutionToolCapability[];
  prohibited_operations: string[];
  metadata: Record<string, unknown>;
};

export type ExecutionCapabilityResponse = {
  ok?: boolean;
  execution_capability?: EngineeringExecutionCapability;
  physical_operations_supported?: boolean;
  error?: string;
  detail?: string;
};

export function summarizeExecutionCapability(report: EngineeringExecutionCapability | null) {
  const operations = report?.operations || [];
  return {
    adapters: operations.length,
    installed: operations.filter((row) => row.tool_installed).length,
    executable: operations.filter((row) => row.executable_under_host_policy).length,
    previewable: operations.filter((row) => row.preview_available).length,
  };
}
