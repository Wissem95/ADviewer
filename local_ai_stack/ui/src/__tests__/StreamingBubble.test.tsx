// Tests StreamingBubble + pipelineStore streaming events — Plan 5B Task 5.
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { StreamingBubble } from "../components/Pipeline/StreamingBubble";
import { usePipelineStore } from "../stores/pipelineStore";

vi.mock("../ws", () => ({
  ws: {
    on: vi.fn(() => () => undefined),
    send: vi.fn(),
  },
}));

describe("StreamingBubble", () => {
  afterEach(() => {
    usePipelineStore.getState().reset();
    vi.clearAllMocks();
  });

  it("ne render rien si streamingBuffer vide", () => {
    render(<StreamingBubble />);
    expect(screen.queryByTestId("streaming-bubble")).toBeNull();
  });

  it("affiche les tokens accumulés progressivement", () => {
    const store = usePipelineStore.getState();

    act(() => {
      store.onChatToken({ token: "Hel", stage: "execute", llm: "minimax/minimax-m2.5" });
      store.onChatToken({ token: "lo ", stage: "execute", llm: "minimax/minimax-m2.5" });
      store.onChatToken({ token: "world", stage: "execute", llm: "minimax/minimax-m2.5" });
    });

    render(<StreamingBubble />);
    expect(screen.getByTestId("streaming-bubble")).toBeInTheDocument();
    expect(screen.getByText(/Hello world/)).toBeInTheDocument();
    expect(screen.getByText(/streaming.*execute/)).toBeInTheDocument();
  });

  it("efface le buffer à la fin du stage (onStageComplete)", () => {
    const store = usePipelineStore.getState();

    act(() => {
      store.onChatToken({ token: "partial", stage: "execute", llm: "minimax/minimax-m2.5" });
    });
    expect(usePipelineStore.getState().streamingBuffer).toBe("partial");

    act(() => {
      store.onStageComplete({
        stage: "execute",
        success: true,
        duration_ms: 1000,
        tokens_in: 100,
        tokens_out: 50,
        cost_usd: 0.001,
        error: null,
      });
    });

    expect(usePipelineStore.getState().streamingBuffer).toBe("");
    expect(usePipelineStore.getState().streamingStage).toBeNull();
  });

  it("reset le buffer quand un nouveau stage commence (onStageStart)", () => {
    const store = usePipelineStore.getState();

    act(() => {
      store.onChatToken({ token: "stale", stage: "ground", llm: "minimax/minimax-m2.5" });
    });
    expect(usePipelineStore.getState().streamingBuffer).toBe("stale");

    act(() => {
      store.onStageStart({ stage: "execute", llm: "minimax/minimax-m2.5" });
    });

    expect(usePipelineStore.getState().streamingBuffer).toBe("");
    expect(usePipelineStore.getState().streamingStage).toBe("execute");
  });

  it("clearStreamingBuffer reset l'état streaming", () => {
    const store = usePipelineStore.getState();

    act(() => {
      store.onChatToken({ token: "xxx", stage: "ground", llm: "deepseek/deepseek-r1" });
    });
    expect(usePipelineStore.getState().streamingBuffer).toBe("xxx");

    act(() => {
      store.clearStreamingBuffer();
    });

    expect(usePipelineStore.getState().streamingBuffer).toBe("");
    expect(usePipelineStore.getState().streamingStage).toBeNull();
    expect(usePipelineStore.getState().streamingLLM).toBeNull();
  });
});
