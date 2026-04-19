import { beforeEach, describe, expect, it, vi } from "vitest";
import { FakeWebSocket } from "../test/setup";

describe("sessionStore", () => {
  beforeEach(() => {
    FakeWebSocket.instances = [];
    vi.resetModules();
  });

  it("valeurs par défaut : branch main, tokens 0, backendStatus connecting", async () => {
    const { useSessionStore } = await import("../stores/sessionStore");
    const s = useSessionStore.getState();
    expect(s.branch).toBe("main");
    expect(s.modifiedFiles).toBe(0);
    expect(s.tokensToday).toBe(0);
    expect(s.estimatedCostUSD).toBe(0);
    expect(s.backendStatus).toBe("connecting");
  });

  it("setBranch met à jour branch et modifiedFiles", async () => {
    const { useSessionStore } = await import("../stores/sessionStore");
    useSessionStore.getState().setBranch("feat/ui", 7);
    expect(useSessionStore.getState().branch).toBe("feat/ui");
    expect(useSessionStore.getState().modifiedFiles).toBe(7);
  });

  it("addTokens accumule tokens et coût", async () => {
    const { useSessionStore } = await import("../stores/sessionStore");
    useSessionStore.getState().addTokens(100, 0.0012);
    useSessionStore.getState().addTokens(50, 0.0005);
    const s = useSessionStore.getState();
    expect(s.tokensToday).toBe(150);
    expect(s.estimatedCostUSD).toBeCloseTo(0.0017, 6);
  });

  it("setBackendStatus bascule l'état", async () => {
    const { useSessionStore } = await import("../stores/sessionStore");
    useSessionStore.getState().setBackendStatus("ready");
    expect(useSessionStore.getState().backendStatus).toBe("ready");
    useSessionStore.getState().setBackendStatus("error");
    expect(useSessionStore.getState().backendStatus).toBe("error");
  });

  it("connectSessionStore : event health passe backendStatus à ready (I7)", async () => {
    const { ws } = await import("../ws");
    const { useSessionStore, connectSessionStore } = await import("../stores/sessionStore");
    const cleanup = connectSessionStore();
    ws.connect();
    FakeWebSocket.instances[0]._triggerOpen();
    expect(useSessionStore.getState().backendStatus).toBe("ready");
    cleanup();
  });

  it("connectSessionStore : bascule à 'connecting' quand la WS se ferme", async () => {
    const { ws } = await import("../ws");
    const { useSessionStore, connectSessionStore } = await import("../stores/sessionStore");
    const cleanup = connectSessionStore();
    ws.connect();
    const sock = FakeWebSocket.instances[0];
    sock._triggerOpen();
    expect(useSessionStore.getState().backendStatus).toBe("ready");
    sock.close();
    expect(useSessionStore.getState().backendStatus).toBe("connecting");
    cleanup();
  });

  it("connectSessionStore : git_status + token_usage", async () => {
    const { ws } = await import("../ws");
    const { useSessionStore, connectSessionStore } = await import("../stores/sessionStore");
    const cleanup = connectSessionStore();
    ws.connect();
    const sock = FakeWebSocket.instances[0];
    sock._triggerOpen();
    sock._triggerMessage("git_status", { branch: "main", modifiedFiles: 3 });
    sock._triggerMessage("token_usage", { tokens: 500, costUSD: 0.01 });
    const s = useSessionStore.getState();
    expect(s.branch).toBe("main");
    expect(s.modifiedFiles).toBe(3);
    expect(s.tokensToday).toBe(500);
    expect(s.estimatedCostUSD).toBeCloseTo(0.01, 6);
    cleanup();
  });
});
