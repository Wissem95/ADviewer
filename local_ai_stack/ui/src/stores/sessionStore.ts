// Session active : tokens, coût estimé, branche git, statut backend.
import { create } from "zustand";
import { ws } from "../ws";

export type BackendStatus = "connecting" | "ready" | "error";

interface SessionStore {
  branch: string;
  modifiedFiles: number;
  tokensToday: number;
  estimatedCostUSD: number;
  backendStatus: BackendStatus;
  setBackendStatus: (s: BackendStatus) => void;
  setBranch: (branch: string, modifiedFiles: number) => void;
  addTokens: (tokens: number, costUSD: number) => void;
}

export const useSessionStore = create<SessionStore>((set) => ({
  branch: "main",
  modifiedFiles: 0,
  tokensToday: 0,
  estimatedCostUSD: 0,
  backendStatus: "connecting",

  setBackendStatus: (backendStatus) => set({ backendStatus }),
  setBranch: (branch, modifiedFiles) => set({ branch, modifiedFiles }),
  addTokens: (tokens, costUSD) =>
    set((state) => ({
      tokensToday: state.tokensToday + tokens,
      estimatedCostUSD: state.estimatedCostUSD + costUSD,
    })),
}));

export function connectSessionStore(): () => void {
  const cleanups = [
    ws.on("health", () => {
      useSessionStore.getState().setBackendStatus("ready");
    }),
    ws.on("disconnect", () => {
      useSessionStore.getState().setBackendStatus("connecting");
    }),
    ws.on("git_status", (data) => {
      const { branch, modifiedFiles } = data as { branch: string; modifiedFiles: number };
      useSessionStore.getState().setBranch(branch, modifiedFiles);
    }),
    ws.on("token_usage", (data) => {
      const { tokens, costUSD } = data as { tokens: number; costUSD: number };
      useSessionStore.getState().addTokens(tokens, costUSD);
    }),
  ];
  return () => cleanups.forEach((c) => c());
}
