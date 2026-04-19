import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FakeWebSocket } from "../test/setup";

describe("WSClient", () => {
  beforeEach(async () => {
    FakeWebSocket.instances = [];
    vi.useFakeTimers();
    vi.resetModules();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("connect() n'ouvre pas une 2e socket si déjà CONNECTING (StrictMode safe)", async () => {
    const { ws } = await import("../ws");
    ws.connect();
    ws.connect();
    ws.connect();
    expect(FakeWebSocket.instances).toHaveLength(1);
  });

  it("connects to ws://127.0.0.1:8765/ws", async () => {
    const { ws } = await import("../ws");
    ws.connect();
    expect(FakeWebSocket.instances.length).toBe(1);
    expect(FakeWebSocket.instances[0].url).toBe("ws://127.0.0.1:8765/ws");
  });

  it("routes typed messages to registered handlers", async () => {
    const { ws } = await import("../ws");
    ws.connect();
    const sock = FakeWebSocket.instances[0];
    const handler = vi.fn();
    ws.on("routing_decision", handler);
    sock._triggerOpen();
    sock._triggerMessage("routing_decision", { llm: "minimax" });
    expect(handler).toHaveBeenCalledWith({ llm: "minimax" });
  });

  it("cleanup function unregisters handler", async () => {
    const { ws } = await import("../ws");
    ws.connect();
    const sock = FakeWebSocket.instances[0];
    const handler = vi.fn();
    const unsub = ws.on("agent_step", handler);
    unsub();
    sock._triggerOpen();
    sock._triggerMessage("agent_step", { step: "PLAN" });
    expect(handler).not.toHaveBeenCalled();
  });

  it("C16 — buffers messages sent before OPEN and flushes on open", async () => {
    const { ws } = await import("../ws");
    ws.connect();
    const sock = FakeWebSocket.instances[0];
    ws.send("chat", { prompt: "hello" });
    expect(sock.sent).toHaveLength(0);
    sock._triggerOpen();
    expect(sock.sent).toHaveLength(1);
    expect(JSON.parse(sock.sent[0])).toEqual({ type: "chat", data: { prompt: "hello" } });
  });

  it("sends directly once connection is OPEN", async () => {
    const { ws } = await import("../ws");
    ws.connect();
    const sock = FakeWebSocket.instances[0];
    sock._triggerOpen();
    ws.send("chat", { prompt: "go" });
    expect(sock.sent).toHaveLength(1);
  });

  it("I7 — fires 'health' handlers on connection open", async () => {
    const { ws } = await import("../ws");
    const healthHandler = vi.fn();
    ws.on("health", healthHandler);
    ws.connect();
    FakeWebSocket.instances[0]._triggerOpen();
    expect(healthHandler).toHaveBeenCalledTimes(1);
  });

  it("auto-reconnects after 2s on close", async () => {
    const { ws } = await import("../ws");
    ws.connect();
    const first = FakeWebSocket.instances[0];
    first._triggerOpen();
    first.close();
    expect(FakeWebSocket.instances).toHaveLength(1);
    vi.advanceTimersByTime(2000);
    expect(FakeWebSocket.instances).toHaveLength(2);
  });

  it("fires 'disconnect' handlers on close (before reconnect)", async () => {
    const { ws } = await import("../ws");
    const onDisconnect = vi.fn();
    ws.on("disconnect", onDisconnect);
    ws.connect();
    const sock = FakeWebSocket.instances[0];
    sock._triggerOpen();
    sock.close();
    expect(onDisconnect).toHaveBeenCalledTimes(1);
  });

  it("re-fires 'health' on second OPEN after reconnect", async () => {
    const { ws } = await import("../ws");
    const onHealth = vi.fn();
    ws.on("health", onHealth);
    ws.connect();
    const first = FakeWebSocket.instances[0];
    first._triggerOpen();
    first.close();
    vi.advanceTimersByTime(2000);
    const second = FakeWebSocket.instances[1];
    second._triggerOpen();
    expect(onHealth).toHaveBeenCalledTimes(2);
  });

  it("#5 — caps pendingMessages at 100 with drop-head", async () => {
    const { ws, MAX_PENDING_MESSAGES } = await import("../ws");
    expect(MAX_PENDING_MESSAGES).toBe(100);
    ws.connect();
    const sock = FakeWebSocket.instances[0];
    for (let i = 0; i < MAX_PENDING_MESSAGES + 5; i++) {
      ws.send("msg", { i });
    }
    sock._triggerOpen();
    // Les 5 premiers ont été droppés ; on doit recevoir de i=5 à i=104.
    expect(sock.sent).toHaveLength(MAX_PENDING_MESSAGES);
    expect(JSON.parse(sock.sent[0])).toEqual({ type: "msg", data: { i: 5 } });
    expect(JSON.parse(sock.sent[sock.sent.length - 1])).toEqual({
      type: "msg",
      data: { i: MAX_PENDING_MESSAGES + 4 },
    });
  });

  it("#15 — dispatches 'error' event on onerror", async () => {
    const { ws } = await import("../ws");
    const onError = vi.fn();
    ws.on("error", onError);
    ws.connect();
    const sock = FakeWebSocket.instances[0];
    const errEvent = new Event("error");
    sock.onerror?.(errEvent);
    expect(onError).toHaveBeenCalledTimes(1);
  });

  it("#4 — dispatches 'error' with a serializable {message} payload, not a DOM Event", async () => {
    const { ws } = await import("../ws");
    const onError = vi.fn();
    ws.on("error", onError);
    ws.connect();
    FakeWebSocket.instances[0].onerror?.(new Event("error"));
    const payload = onError.mock.calls[0][0];
    // Pas un Event DOM (qui JSON.stringify en "{}")
    expect(payload).not.toBeInstanceOf(Event);
    expect(typeof payload).toBe("object");
    expect(payload).toHaveProperty("message");
    expect(typeof payload.message).toBe("string");
    expect(payload.message.length).toBeGreaterThan(0);
  });

  it("ignores non-JSON messages silently", async () => {
    const { ws } = await import("../ws");
    ws.connect();
    const sock = FakeWebSocket.instances[0];
    const handler = vi.fn();
    ws.on("anything", handler);
    sock._triggerOpen();
    sock.onmessage?.({ data: "not json" });
    expect(handler).not.toHaveBeenCalled();
  });
});
