// Tests TraceViewer — Plan 5A Task 13.
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { TraceViewer } from "../components/Pipeline/TraceViewer";
import { usePipelineStore } from "../stores/pipelineStore";
import type { EstimateResult } from "../types/pipeline";

vi.mock("../ws", () => ({
  ws: {
    on: vi.fn(() => () => undefined),
    send: vi.fn(),
  },
}));

const sampleEstimate: EstimateResult = {
  estimateId: "est-1",
  classification: "simple",
  reason: "Tâche directe",
  stages: [
    {
      name: "estimate",
      llm: "gemini/gemini-2.5-flash",
      tokensIn: 100,
      tokensOut: 50,
      costUSD: 0.0001,
      durationSec: 0.5,
    },
    {
      name: "execute",
      llm: "minimax/minimax-m2.5",
      tokensIn: 500,
      tokensOut: 300,
      costUSD: 0.005,
      durationSec: 2.0,
    },
  ],
  totalCostUSD: 0.0051,
  totalDurationSec: 2.5,
};

describe("TraceViewer", () => {
  afterEach(() => {
    usePipelineStore.getState().reset();
    vi.clearAllMocks();
  });

  it("ne render rien si pas d'estimate", () => {
    render(<TraceViewer />);
    expect(screen.queryByTestId("trace-viewer")).toBeNull();
  });

  it("ne render rien tant que modal en attente de confirmation", () => {
    usePipelineStore.getState().onEstimateReceived(sampleEstimate);
    render(<TraceViewer />);
    expect(screen.queryByTestId("trace-viewer")).toBeNull();
  });

  it("render après confirmation avec stages pending", () => {
    usePipelineStore.getState().onEstimateReceived(sampleEstimate);
    usePipelineStore.getState().confirm();
    render(<TraceViewer />);
    expect(screen.getByTestId("trace-viewer")).toBeInTheDocument();
    expect(screen.getByText(/Pipeline simple/)).toBeInTheDocument();
    expect(screen.getByText("0/2 étapes")).toBeInTheDocument();
    expect(screen.getByTestId("stage-row-estimate")).toBeInTheDocument();
    expect(screen.getByTestId("stage-row-execute")).toBeInTheDocument();
  });

  it("update le compteur quand stage_complete arrive", () => {
    const store = usePipelineStore.getState();
    store.onEstimateReceived(sampleEstimate);
    store.confirm();
    store.onStageStart({ stage: "estimate", llm: "gemini/gemini-2.5-flash" });
    store.onStageComplete({
      stage: "estimate",
      success: true,
      duration_ms: 500,
      tokens_in: 100,
      tokens_out: 50,
      cost_usd: 0.0001,
      error: null,
    });
    render(<TraceViewer />);
    expect(screen.getByText("1/2 étapes")).toBeInTheDocument();
  });

  it("affiche bouton Stop tant que pipeline en cours", () => {
    const store = usePipelineStore.getState();
    store.onEstimateReceived(sampleEstimate);
    store.confirm();
    render(<TraceViewer />);
    expect(screen.getByText("Stop")).toBeInTheDocument();
    expect(screen.getByText(/⌘\./)).toBeInTheDocument();
  });

  it("clic Stop envoie pipeline_stop via ws.send", async () => {
    const { ws } = await import("../ws");
    const store = usePipelineStore.getState();
    store.onEstimateReceived(sampleEstimate);
    store.confirm();
    render(<TraceViewer />);

    const stopBtn = screen.getByText("Stop");
    stopBtn.click();

    expect(ws.send).toHaveBeenCalledWith("pipeline_stop", { reason: "button" });
  });

  it("Cmd+. envoie pipeline_stop via raccourci clavier", async () => {
    const { ws } = await import("../ws");
    const store = usePipelineStore.getState();
    store.onEstimateReceived(sampleEstimate);
    store.confirm();
    render(<TraceViewer />);

    window.dispatchEvent(
      new KeyboardEvent("keydown", { key: ".", metaKey: true }),
    );

    expect(ws.send).toHaveBeenCalledWith("pipeline_stop", { reason: "shortcut" });
  });

  it("affiche succès final quand pipeline_complete success", () => {
    const store = usePipelineStore.getState();
    store.onEstimateReceived(sampleEstimate);
    store.confirm();
    store.onPipelineComplete({
      success: true,
      filesModified: ["hello.py"],
      totalCostUSD: 0.005,
      totalDurationMs: 2500,
      rollbackPerformed: false,
      error: null,
    });
    render(<TraceViewer />);
    expect(screen.getByText(/Pipeline terminé/)).toBeInTheDocument();
    expect(screen.queryByText("Stop")).toBeNull();
  });

  it("affiche échec + rollback quand applicable", () => {
    const store = usePipelineStore.getState();
    store.onEstimateReceived(sampleEstimate);
    store.confirm();
    store.onPipelineRollback({ reason: "Tests rouges après 3 retries" });
    render(<TraceViewer />);
    expect(screen.getByText(/rollback effectué/)).toBeInTheDocument();
    expect(screen.getByText(/Tests rouges après 3 retries/)).toBeInTheDocument();
  });
});
