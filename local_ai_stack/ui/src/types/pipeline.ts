// Types pipeline alignés sur backend/pipeline/types.py + cost_estimator.py.
// Plan 5A Task 12.

export type PipelineMode = "simple" | "medium" | "complex";

export type StageStatus = "pending" | "running" | "done" | "failed";

export interface StageEstimate {
  name: string;
  llm: string;
  tokensIn: number;
  tokensOut: number;
  costUSD: number;
  durationSec: number;
}

export interface EstimateResult {
  estimateId: string;
  classification: PipelineMode;
  reason: string;
  stages: StageEstimate[];
  totalCostUSD: number;
  totalDurationSec: number;
}

export interface StageProgress {
  name: string;
  llm: string | null;
  status: StageStatus;
  durationMs: number;
  tokensIn: number;
  tokensOut: number;
  costUSD: number;
  error: string | null;
}

export interface PipelineResultPayload {
  success: boolean;
  filesModified: string[];
  totalCostUSD: number;
  totalDurationMs: number;
  rollbackPerformed: boolean;
  error: string | null;
}

// Plan 5C Task 2 : ChallengeResult aligné sur backend dataclass.
export type ChallengeSeverity = "minor" | "moderate" | "critical";

export interface ChallengeResultPayload {
  risks: string[];
  edgeCases: string[];
  alternatives: string[];
  severity: ChallengeSeverity;
  blocking: boolean;
}

// Plan 5C Task 4 : PlanResult aligné sur backend.
export type PlanOperation = "edit" | "create" | "patch" | "delete";
export type PlanRisk = "low" | "medium" | "high";

export interface PlanChangePayload {
  file: string;
  operation: PlanOperation;
  description: string;
  intendedDiffSummary: string;
}

export interface PlanResultPayload {
  changes: PlanChangePayload[];
  testsToRun: string[];
  rollbackStrategy: string;
  rationale: string;
  estimatedRisk: PlanRisk;
  complexityConfirm: number;
}

// Plan 5C Task 7 : deadlock consensus payload (event WS pipeline_user_decision_needed).
export interface DeadlockPayload {
  plans: PlanResultPayload[];
  concerns: string[][];
}
