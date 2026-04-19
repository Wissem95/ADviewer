import { beforeEach, describe, expect, it, vi } from "vitest";
import { FakeWebSocket } from "../test/setup";

describe("llmStore", () => {
  beforeEach(() => {
    FakeWebSocket.instances = [];
    vi.resetModules();
  });

  it("#12 — DEFAULT_LLMS est exporté et correspond à l'état initial", async () => {
    const { DEFAULT_LLMS, useLLMStore } = await import("../stores/llmStore");
    expect(DEFAULT_LLMS).toHaveLength(5);
    expect(useLLMStore.getState().llms.map((l) => l.id)).toEqual(
      DEFAULT_LLMS.map((l) => l.id),
    );
  });

  it("initialise 5 LLMs par défaut avec status idle", async () => {
    const { useLLMStore } = await import("../stores/llmStore");
    const llms = useLLMStore.getState().llms;
    expect(llms).toHaveLength(5);
    expect(llms.map((l) => l.id)).toEqual([
      "minimax/minimax-m2.5",
      "gemini/gemini-2.5-pro",
      "gemini/gemini-2.5-flash",
      "deepseek/deepseek-r1",
      "mistral/codestral-2",
    ]);
    expect(llms.every((l) => l.status === "idle")).toBe(true);
  });

  it("setStatus met à jour status + currentTask d'un seul LLM", async () => {
    const { useLLMStore } = await import("../stores/llmStore");
    useLLMStore.getState().setStatus("minimax/minimax-m2.5", "busy", "coding task");
    const minimax = useLLMStore.getState().llms.find((l) => l.id === "minimax/minimax-m2.5");
    expect(minimax?.status).toBe("busy");
    expect(minimax?.currentTask).toBe("coding task");
    const other = useLLMStore.getState().llms.find((l) => l.id === "deepseek/deepseek-r1");
    expect(other?.status).toBe("idle");
  });

  it("setDisabled bascule entre disabled et idle", async () => {
    const { useLLMStore } = await import("../stores/llmStore");
    useLLMStore.getState().setDisabled("gemini/gemini-2.5-pro", true);
    expect(useLLMStore.getState().llms.find((l) => l.id === "gemini/gemini-2.5-pro")?.status).toBe("disabled");
    useLLMStore.getState().setDisabled("gemini/gemini-2.5-pro", false);
    expect(useLLMStore.getState().llms.find((l) => l.id === "gemini/gemini-2.5-pro")?.status).toBe("idle");
  });

  it("updateTokens accumule les tokens par LLM", async () => {
    const { useLLMStore } = await import("../stores/llmStore");
    useLLMStore.getState().updateTokens("mistral/codestral-2", 100);
    useLLMStore.getState().updateTokens("mistral/codestral-2", 50);
    expect(useLLMStore.getState().llms.find((l) => l.id === "mistral/codestral-2")?.tokensToday).toBe(150);
  });

  it("updateLatency remplace la latence (pas d'accumulation)", async () => {
    const { useLLMStore } = await import("../stores/llmStore");
    useLLMStore.getState().updateLatency("deepseek/deepseek-r1", 1200);
    useLLMStore.getState().updateLatency("deepseek/deepseek-r1", 800);
    expect(useLLMStore.getState().llms.find((l) => l.id === "deepseek/deepseek-r1")?.latencyMs).toBe(800);
  });

  it("connectLLMStore : llm_status met à jour le store", async () => {
    const { ws } = await import("../ws");
    const { useLLMStore, connectLLMStore } = await import("../stores/llmStore");
    ws.connect();
    const cleanup = connectLLMStore();
    const sock = FakeWebSocket.instances[0];
    sock._triggerOpen();
    sock._triggerMessage("llm_status", { id: "minimax/minimax-m2.5", status: "busy", task: "tests" });
    expect(useLLMStore.getState().llms.find((l) => l.id === "minimax/minimax-m2.5")?.status).toBe("busy");
    cleanup();
  });

  it("connectLLMStore : llm_tokens accumule via store", async () => {
    const { ws } = await import("../ws");
    const { useLLMStore, connectLLMStore } = await import("../stores/llmStore");
    ws.connect();
    const cleanup = connectLLMStore();
    const sock = FakeWebSocket.instances[0];
    sock._triggerOpen();
    sock._triggerMessage("llm_tokens", { id: "gemini/gemini-2.5-flash", tokens: 200 });
    sock._triggerMessage("llm_tokens", { id: "gemini/gemini-2.5-flash", tokens: 300 });
    expect(useLLMStore.getState().llms.find((l) => l.id === "gemini/gemini-2.5-flash")?.tokensToday).toBe(500);
    cleanup();
  });
});
