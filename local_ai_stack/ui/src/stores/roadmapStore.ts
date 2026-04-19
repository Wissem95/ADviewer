// Roadmap projet courante — synchronisée depuis le backend.
import { create } from "zustand";
import { ws } from "../ws";

export interface SubTask {
  id: string;
  text: string;
  done: boolean;
}

export interface RoadmapTask {
  id: string;
  title: string;
  status: "pending" | "in_progress" | "done" | "failed" | "blocked";
  assignedTo: string;
  subtasks: SubTask[];
  sprint: string;
  estimatedComplexity: number;
  githubIssue: number | null;
}

export interface Roadmap {
  project: string;
  sessionId: string;
  tasks: RoadmapTask[];
}

interface RoadmapStore {
  roadmap: Roadmap | null;
  setRoadmap: (roadmap: Roadmap) => void;
  clearRoadmap: () => void;
  updateTaskStatus: (taskId: string, status: RoadmapTask["status"]) => void;
}

export const useRoadmapStore = create<RoadmapStore>((set) => ({
  roadmap: null,
  setRoadmap: (roadmap) => set({ roadmap }),
  clearRoadmap: () => set({ roadmap: null }),
  updateTaskStatus: (taskId, status) =>
    set((state) => {
      if (!state.roadmap) return state;
      return {
        roadmap: {
          ...state.roadmap,
          tasks: state.roadmap.tasks.map((t) =>
            t.id === taskId ? { ...t, status } : t,
          ),
        },
      };
    }),
}));

export function connectRoadmapStore(): () => void {
  const cleanups = [
    ws.on("roadmap_update", (data) => {
      useRoadmapStore.getState().setRoadmap(data as Roadmap);
    }),
    ws.on("task_status", (data) => {
      const { id, status } = data as { id: string; status: RoadmapTask["status"] };
      useRoadmapStore.getState().updateTaskStatus(id, status);
    }),
    ws.on("project_mode_off", () => {
      useRoadmapStore.getState().clearRoadmap();
    }),
  ];
  return () => cleanups.forEach((c) => c());
}
