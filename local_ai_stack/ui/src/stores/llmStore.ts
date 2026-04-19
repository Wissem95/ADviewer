// Statut temps réel des LLMs — mis à jour via WebSocket.
import { create } from "zustand";
import { ws } from "../ws";

export type LLMStatus = "idle" | "busy" | "disabled" | "error";

export interface LLMInfo {
  id: string;
  name: string;
  role: string;
  status: LLMStatus;
  currentTask: string | null;
  tokensToday: number;
  latencyMs: number;
}

interface LLMStore {
  llms: LLMInfo[];
  setStatus: (id: string, status: LLMStatus, task?: string) => void;
  setDisabled: (id: string, disabled: boolean) => void;
  updateTokens: (id: string, tokens: number) => void;
  updateLatency: (id: string, latencyMs: number) => void;
}

const DEFAULT_LLMS: LLMInfo[] = [
  { id: "minimax/minimax-m2.5", name: "MiniMax M2.5", role: "coding", status: "idle", currentTask: null, tokensToday: 0, latencyMs: 0 },
  { id: "gemini/gemini-2.5-pro", name: "Gemini Pro", role: "analysis", status: "idle", currentTask: null, tokensToday: 0, latencyMs: 0 },
  { id: "gemini/gemini-2.5-flash", name: "Gemini Flash", role: "routing", status: "idle", currentTask: null, tokensToday: 0, latencyMs: 0 },
  { id: "deepseek/deepseek-r1", name: "DeepSeek R1", role: "architecture", status: "idle", currentTask: null, tokensToday: 0, latencyMs: 0 },
  { id: "mistral/codestral-2", name: "Codestral 2", role: "testing", status: "idle", currentTask: null, tokensToday: 0, latencyMs: 0 },
];

export const useLLMStore = create<LLMStore>((set) => ({
  llms: DEFAULT_LLMS,

  setStatus: (id, status, task) =>
    set((state) => ({
      llms: state.llms.map((llm) =>
        llm.id === id ? { ...llm, status, currentTask: task ?? llm.currentTask } : llm,
      ),
    })),

  setDisabled: (id, disabled) =>
    set((state) => ({
      llms: state.llms.map((llm) =>
        llm.id === id ? { ...llm, status: disabled ? "disabled" : "idle" } : llm,
      ),
    })),

  updateTokens: (id, tokens) =>
    set((state) => ({
      llms: state.llms.map((llm) =>
        llm.id === id ? { ...llm, tokensToday: llm.tokensToday + tokens } : llm,
      ),
    })),

  updateLatency: (id, latencyMs) =>
    set((state) => ({
      llms: state.llms.map((llm) =>
        llm.id === id ? { ...llm, latencyMs } : llm,
      ),
    })),
}));

export function connectLLMStore(): () => void {
  const cleanups = [
    ws.on("llm_status", (data) => {
      const { id, status, task } = data as { id: string; status: LLMStatus; task?: string };
      useLLMStore.getState().setStatus(id, status, task);
    }),
    ws.on("llm_tokens", (data) => {
      const { id, tokens } = data as { id: string; tokens: number };
      useLLMStore.getState().updateTokens(id, tokens);
    }),
    ws.on("llm_latency", (data) => {
      const { id, latencyMs } = data as { id: string; latencyMs: number };
      useLLMStore.getState().updateLatency(id, latencyMs);
    }),
  ];
  return () => cleanups.forEach((c) => c());
}
