import { beforeEach, describe, expect, it, vi } from "vitest";
import { FakeWebSocket } from "../test/setup";

const baseEntry = (id: string) => ({
  id,
  timestamp: Date.now(),
  prompt: `prompt-${id}`,
  llm: "minimax/minimax-m2.5",
  role: "coding",
  mode: "medium",
  reason: "test",
  durationMs: 100,
  tokens: 50,
});

describe("routingStore", () => {
  beforeEach(() => {
    FakeWebSocket.instances = [];
    vi.resetModules();
  });

  it("history vide au démarrage, live null", async () => {
    const { useRoutingStore } = await import("../stores/routingStore");
    expect(useRoutingStore.getState().history).toEqual([]);
    expect(useRoutingStore.getState().live).toBeNull();
  });

  it("addEntry empile en tête (LIFO) et plafonne à MAX_HISTORY", async () => {
    const { useRoutingStore, MAX_HISTORY } = await import("../stores/routingStore");
    for (let i = 0; i < MAX_HISTORY + 10; i++) {
      useRoutingStore.getState().addEntry(baseEntry(`e${i}`));
    }
    const h = useRoutingStore.getState().history;
    expect(h).toHaveLength(MAX_HISTORY);
    expect(h[0].id).toBe(`e${MAX_HISTORY + 9}`);
    expect(h[h.length - 1].id).toBe("e10");
  });

  it("setLive met à jour l'état live (ou null)", async () => {
    const { useRoutingStore } = await import("../stores/routingStore");
    useRoutingStore.getState().setLive({ prompt: "p", llm: "minimax", step: "PLAN", attempt: 1 });
    expect(useRoutingStore.getState().live?.step).toBe("PLAN");
    useRoutingStore.getState().setLive(null);
    expect(useRoutingStore.getState().live).toBeNull();
  });

  it("connectRoutingStore : routing_decision ajoute à history et initialise live PLAN", async () => {
    const { ws } = await import("../ws");
    const { useRoutingStore, connectRoutingStore } = await import("../stores/routingStore");
    ws.connect();
    const cleanup = connectRoutingStore();
    const sock = FakeWebSocket.instances[0];
    sock._triggerOpen();
    sock._triggerMessage("routing_decision", baseEntry("r1"));
    expect(useRoutingStore.getState().history).toHaveLength(1);
    expect(useRoutingStore.getState().live?.step).toBe("PLAN");
    expect(useRoutingStore.getState().live?.attempt).toBe(1);
    cleanup();
  });

  it("connectRoutingStore : agent_step met à jour live uniquement si live existe", async () => {
    const { ws } = await import("../ws");
    const { useRoutingStore, connectRoutingStore } = await import("../stores/routingStore");
    ws.connect();
    const cleanup = connectRoutingStore();
    const sock = FakeWebSocket.instances[0];
    sock._triggerOpen();
    // Sans live → agent_step no-op
    sock._triggerMessage("agent_step", { step: "EXECUTE", attempt: 2 });
    expect(useRoutingStore.getState().live).toBeNull();
    // Avec live → agent_step modifie
    sock._triggerMessage("routing_decision", baseEntry("r1"));
    sock._triggerMessage("agent_step", { step: "EXECUTE", attempt: 2 });
    expect(useRoutingStore.getState().live?.step).toBe("EXECUTE");
    expect(useRoutingStore.getState().live?.attempt).toBe(2);
    cleanup();
  });

  it("connectRoutingStore : task_complete clear live", async () => {
    const { ws } = await import("../ws");
    const { useRoutingStore, connectRoutingStore } = await import("../stores/routingStore");
    ws.connect();
    const cleanup = connectRoutingStore();
    const sock = FakeWebSocket.instances[0];
    sock._triggerOpen();
    sock._triggerMessage("routing_decision", baseEntry("r1"));
    sock._triggerMessage("task_complete", {});
    expect(useRoutingStore.getState().live).toBeNull();
    // history inchangée
    expect(useRoutingStore.getState().history).toHaveLength(1);
    cleanup();
  });
});
