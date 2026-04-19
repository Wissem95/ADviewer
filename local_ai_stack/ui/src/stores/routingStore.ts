// Historique et décision live de routing — mis à jour via WebSocket.
import { create } from "zustand";
import { ws } from "../ws";

export interface RoutingEntry {
  id: string;
  timestamp: number;
  prompt: string;
  llm: string;
  role: string;
  mode: string;
  reason: string;
  durationMs: number;
  tokens: number;
}

export interface LiveRouting {
  prompt: string;
  llm: string;
  step: string;
  attempt: number;
}

interface RoutingStore {
  history: RoutingEntry[];
  live: LiveRouting | null;
  addEntry: (entry: RoutingEntry) => void;
  setLive: (live: LiveRouting | null) => void;
}

export const MAX_HISTORY = 100;

export const useRoutingStore = create<RoutingStore>((set) => ({
  history: [],
  live: null,

  addEntry: (entry) =>
    set((state) => ({
      history: [entry, ...state.history].slice(0, MAX_HISTORY),
    })),

  setLive: (live) => set({ live }),
}));

export function connectRoutingStore(): () => void {
  const cleanups = [
    ws.on("routing_decision", (data) => {
      const entry = data as RoutingEntry;
      useRoutingStore.getState().addEntry(entry);
      useRoutingStore.getState().setLive({
        prompt: entry.prompt,
        llm: entry.llm,
        step: "PLAN",
        attempt: 1,
      });
    }),
    ws.on("agent_step", (data) => {
      const { step, attempt } = data as { step: string; attempt: number };
      const state = useRoutingStore.getState();
      if (state.live) {
        state.setLive({ ...state.live, step, attempt });
      }
    }),
    ws.on("task_complete", () => {
      useRoutingStore.getState().setLive(null);
    }),
  ];
  return () => cleanups.forEach((c) => c());
}
