import { beforeEach, describe, expect, it, vi } from "vitest";
import { FakeWebSocket } from "../test/setup";

const sampleRoadmap = {
  project: "demo",
  sessionId: "s1",
  tasks: [
    {
      id: "t1",
      title: "Init",
      status: "pending" as const,
      assignedTo: "minimax/minimax-m2.5",
      subtasks: [],
      sprint: "v1",
      estimatedComplexity: 3,
      githubIssue: null,
    },
    {
      id: "t2",
      title: "Tests",
      status: "in_progress" as const,
      assignedTo: "mistral/codestral-2",
      subtasks: [],
      sprint: "v1",
      estimatedComplexity: 2,
      githubIssue: null,
    },
  ],
};

describe("roadmapStore", () => {
  beforeEach(() => {
    FakeWebSocket.instances = [];
    vi.resetModules();
  });

  it("roadmap null au démarrage", async () => {
    const { useRoadmapStore } = await import("../stores/roadmapStore");
    expect(useRoadmapStore.getState().roadmap).toBeNull();
  });

  it("setRoadmap + clearRoadmap", async () => {
    const { useRoadmapStore } = await import("../stores/roadmapStore");
    useRoadmapStore.getState().setRoadmap(sampleRoadmap);
    expect(useRoadmapStore.getState().roadmap?.tasks).toHaveLength(2);
    useRoadmapStore.getState().clearRoadmap();
    expect(useRoadmapStore.getState().roadmap).toBeNull();
  });

  it("updateTaskStatus no-op quand roadmap null", async () => {
    const { useRoadmapStore } = await import("../stores/roadmapStore");
    useRoadmapStore.getState().updateTaskStatus("t1", "done");
    expect(useRoadmapStore.getState().roadmap).toBeNull();
  });

  it("updateTaskStatus modifie la task ciblée sans toucher aux autres", async () => {
    const { useRoadmapStore } = await import("../stores/roadmapStore");
    useRoadmapStore.getState().setRoadmap(sampleRoadmap);
    useRoadmapStore.getState().updateTaskStatus("t1", "done");
    const tasks = useRoadmapStore.getState().roadmap!.tasks;
    expect(tasks.find((t) => t.id === "t1")?.status).toBe("done");
    expect(tasks.find((t) => t.id === "t2")?.status).toBe("in_progress");
  });

  it("connectRoadmapStore : roadmap_update remplit le store", async () => {
    const { ws } = await import("../ws");
    const { useRoadmapStore, connectRoadmapStore } = await import("../stores/roadmapStore");
    ws.connect();
    const cleanup = connectRoadmapStore();
    const sock = FakeWebSocket.instances[0];
    sock._triggerOpen();
    sock._triggerMessage("roadmap_update", sampleRoadmap);
    expect(useRoadmapStore.getState().roadmap?.project).toBe("demo");
    cleanup();
  });

  it("connectRoadmapStore : task_status patche la task", async () => {
    const { ws } = await import("../ws");
    const { useRoadmapStore, connectRoadmapStore } = await import("../stores/roadmapStore");
    ws.connect();
    const cleanup = connectRoadmapStore();
    const sock = FakeWebSocket.instances[0];
    sock._triggerOpen();
    sock._triggerMessage("roadmap_update", sampleRoadmap);
    sock._triggerMessage("task_status", { id: "t2", status: "done" });
    expect(useRoadmapStore.getState().roadmap!.tasks.find((t) => t.id === "t2")?.status).toBe("done");
    cleanup();
  });

  it("connectRoadmapStore : project_mode_off clear la roadmap", async () => {
    const { ws } = await import("../ws");
    const { useRoadmapStore, connectRoadmapStore } = await import("../stores/roadmapStore");
    ws.connect();
    const cleanup = connectRoadmapStore();
    const sock = FakeWebSocket.instances[0];
    sock._triggerOpen();
    sock._triggerMessage("roadmap_update", sampleRoadmap);
    sock._triggerMessage("project_mode_off", {});
    expect(useRoadmapStore.getState().roadmap).toBeNull();
    cleanup();
  });
});
