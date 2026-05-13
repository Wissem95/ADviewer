// Store pipeline Zustand — state pipeline actif + listeners WS.
// Plan 5A Task 12.
//
// Flow :
// 1. Backend émet `pipeline_estimate` → onEstimateReceived (modal ouverte).
// 2. User clique Lancer → confirm() qui ws.send("pipeline_confirmed").
// 3. Backend itère stages → events stage_start / stage_complete.
// 4. Final → pipeline_complete ou pipeline_rollback.
import { create } from "zustand";
import { ws } from "../ws";
import type {
  ChallengeResultPayload,
  ConsensusRound,
  DeadlockPayload,
  EstimateResult,
  PipelineMode,
  PipelineResultPayload,
  PlanResultPayload,
  StageProgress,
  StageStatus,
} from "../types/pipeline";

interface PipelineStore {
  estimate: EstimateResult | null;
  isAwaitingConfirmation: boolean;
  currentStageName: string | null;
  stages: StageProgress[];
  totalCostUSD: number;
  finalResult: PipelineResultPayload | null;
  // Plan 5B Task 5 : buffer du token-stream en cours (vidé sur stage_complete).
  streamingBuffer: string;
  streamingStage: string | null;
  streamingLLM: string | null;
  // Plan 5C Task 2 : challenge state (Stage2Challenge result + banner blocking).
  challenge: ChallengeResultPayload | null;
  challengeBlocking: boolean;
  // Plan 5C Task 4 : plan state (Stage4aPlan result).
  plan: PlanResultPayload | null;
  // Plan 5C Task 7 : deadlock consensus (2 plans à choisir).
  deadlock: DeadlockPayload | null;
  // Plan 5C Task 9 : log des rounds consensus (R1 ↔ Pro).
  consensusRounds: ConsensusRound[];

  onEstimateReceived: (estimate: EstimateResult) => void;
  confirm: (mode?: PipelineMode) => void;
  cancel: () => void;
  onStageStart: (data: { stage: string; llm: string | null }) => void;
  onStageComplete: (data: {
    stage: string;
    success: boolean;
    duration_ms: number;
    tokens_in: number;
    tokens_out: number;
    cost_usd: number;
    error: string | null;
  }) => void;
  onPipelineComplete: (result: PipelineResultPayload) => void;
  onPipelineRollback: (data: { reason: string }) => void;
  onChatToken: (data: { token: string; stage: string; llm: string | null }) => void;
  clearStreamingBuffer: () => void;
  // Plan 5B Task 6 : Stop pendant exécution (cancellation côté backend).
  stop: (reason?: string) => void;
  // Plan 5C Task 2 : handlers challenge.
  onChallengeResult: (data: ChallengeResultPayload) => void;
  onChallengeBlocking: (data: { severity: string; risks: string[] }) => void;
  acknowledgeBlocking: () => void;
  // Plan 5C Task 4 : handler plan.
  onPlanResult: (data: PlanResultPayload) => void;
  // Plan 5C Task 7 : handlers deadlock.
  onDeadlock: (data: DeadlockPayload) => void;
  resolveDeadlock: (choice: "plan1" | "plan2" | "cancel") => void;
  // Plan 5C Task 9 : handler consensus rounds.
  onConsensusRound: (data: ConsensusRound) => void;
  reset: () => void;
}

const initialState = {
  estimate: null,
  isAwaitingConfirmation: false,
  currentStageName: null,
  stages: [] as StageProgress[],
  totalCostUSD: 0,
  finalResult: null,
  streamingBuffer: "",
  streamingStage: null as string | null,
  streamingLLM: null as string | null,
  challenge: null as ChallengeResultPayload | null,
  challengeBlocking: false,
  plan: null as PlanResultPayload | null,
  deadlock: null as DeadlockPayload | null,
  consensusRounds: [] as ConsensusRound[],
};

export const usePipelineStore = create<PipelineStore>((set, get) => ({
  ...initialState,

  onEstimateReceived: (estimate) => {
    const stages: StageProgress[] = estimate.stages.map((s) => ({
      name: s.name,
      llm: s.llm,
      status: "pending" as StageStatus,
      durationMs: 0,
      tokensIn: 0,
      tokensOut: 0,
      costUSD: 0,
      error: null,
    }));
    set({
      estimate,
      isAwaitingConfirmation: true,
      stages,
      totalCostUSD: 0,
      finalResult: null,
      currentStageName: null,
    });
  },

  confirm: (mode) => {
    const estimate = get().estimate;
    if (!estimate) return;
    ws.send("pipeline_confirmed", {
      estimate_id: estimate.estimateId,
      mode: mode ?? estimate.classification,
    });
    set({ isAwaitingConfirmation: false });
  },

  cancel: () => {
    ws.send("pipeline_cancelled", {
      estimate_id: get().estimate?.estimateId ?? null,
    });
    set({ ...initialState });
  },

  onStageStart: ({ stage, llm }) => {
    set((state) => ({
      currentStageName: stage,
      // Reset du buffer streaming pour ce nouveau stage.
      streamingBuffer: "",
      streamingStage: stage,
      streamingLLM: llm,
      stages: state.stages.map((s) =>
        s.name === stage ? { ...s, status: "running" as StageStatus, llm: llm ?? s.llm } : s,
      ),
    }));
  },

  onStageComplete: (data) => {
    set((state) => {
      const status: StageStatus = data.success ? "done" : "failed";
      const updated = state.stages.map((s) =>
        s.name === data.stage
          ? {
              ...s,
              status,
              durationMs: data.duration_ms,
              tokensIn: data.tokens_in,
              tokensOut: data.tokens_out,
              costUSD: data.cost_usd,
              error: data.error,
            }
          : s,
      );
      return {
        stages: updated,
        totalCostUSD: state.totalCostUSD + (data.cost_usd ?? 0),
        // Fige le buffer (efface) à la fin du stage.
        streamingBuffer: "",
        streamingStage: null,
        streamingLLM: null,
      };
    });
  },

  onChatToken: ({ token, stage, llm }) => {
    set((state) => ({
      streamingBuffer: state.streamingBuffer + token,
      streamingStage: stage,
      streamingLLM: llm ?? state.streamingLLM,
    }));
  },

  clearStreamingBuffer: () => {
    set({ streamingBuffer: "", streamingStage: null, streamingLLM: null });
  },

  stop: (reason = "user") => {
    ws.send("pipeline_stop", { reason });
  },

  onChallengeResult: (data) => {
    set({ challenge: data });
  },

  onChallengeBlocking: () => {
    set({ challengeBlocking: true });
  },

  acknowledgeBlocking: () => {
    set({ challengeBlocking: false });
  },

  onPlanResult: (data) => {
    set({ plan: data });
  },

  onDeadlock: (data) => {
    set({ deadlock: data });
  },

  resolveDeadlock: (choice) => {
    const state = get();
    ws.send("user_decision", {
      type: "plan_deadlock",
      choice,
      plans_count: state.deadlock?.plans.length ?? 0,
    });
    set({ deadlock: null });
    if (choice === "cancel") {
      ws.send("pipeline_stop", { reason: "deadlock-cancelled" });
    }
  },

  onConsensusRound: (data) => {
    set((state) => ({
      consensusRounds: [...state.consensusRounds, data],
    }));
  },

  onPipelineComplete: (result) => {
    set({ finalResult: result, currentStageName: null });
  },

  onPipelineRollback: ({ reason }) => {
    set((state) => ({
      finalResult: {
        success: false,
        filesModified: [],
        totalCostUSD: state.totalCostUSD,
        totalDurationMs: 0,
        rollbackPerformed: true,
        error: reason,
      },
    }));
  },

  reset: () => set({ ...initialState }),
}));

export function connectPipelineStore(): () => void {
  const store = usePipelineStore.getState();
  const cleanups = [
    ws.on("pipeline_estimate", (data) => {
      store.onEstimateReceived(data as EstimateResult);
    }),
    ws.on("stage_start", (data) => {
      store.onStageStart(data as { stage: string; llm: string | null });
    }),
    ws.on("stage_complete", (data) => {
      store.onStageComplete(
        data as {
          stage: string;
          success: boolean;
          duration_ms: number;
          tokens_in: number;
          tokens_out: number;
          cost_usd: number;
          error: string | null;
        },
      );
    }),
    ws.on("pipeline_complete", (data) => {
      store.onPipelineComplete(data as PipelineResultPayload);
    }),
    ws.on("pipeline_rollback", (data) => {
      store.onPipelineRollback(data as { reason: string });
    }),
    ws.on("chat_token", (data) => {
      store.onChatToken(
        data as { token: string; stage: string; llm: string | null },
      );
    }),
    ws.on("challenge_blocking", (data) => {
      store.onChallengeBlocking(
        data as { severity: string; risks: string[] },
      );
    }),
    ws.on("pipeline_user_decision_needed", (data) => {
      const msg = data as { type?: string; plans?: unknown[]; concerns?: unknown[] };
      if (msg.type === "plan_deadlock") {
        store.onDeadlock({
          plans: (msg.plans ?? []) as PlanResultPayload[],
          concerns: (msg.concerns ?? []) as string[][],
        });
      }
    }),
    ws.on("consensus_round", (data) => {
      const msg = data as {
        round: number;
        verdict: ConsensusRound["verdict"];
        plan_summary: ConsensusRound["planSummary"];
        concerns: string[];
      };
      store.onConsensusRound({
        round: msg.round,
        verdict: msg.verdict,
        planSummary: msg.plan_summary,
        concerns: msg.concerns ?? [],
      });
    }),
  ];
  return () => cleanups.forEach((fn) => fn());
}
