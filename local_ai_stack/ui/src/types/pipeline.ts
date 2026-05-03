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
