// Tests EstimateModal — Plan 5A Task 12.
import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { EstimateModal } from "../components/Pipeline/EstimateModal";
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
  reason: "Tâche directe : créer un fichier",
  stages: [
    {
      name: "estimate",
      llm: "gemini/gemini-2.5-flash",
      tokensIn: 200,
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

describe("EstimateModal", () => {
  afterEach(() => {
    usePipelineStore.getState().reset();
    vi.clearAllMocks();
  });

  it("ne render rien si non ouvert", () => {
    render(<EstimateModal />);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("affiche classification, raison, étapes et bouton Lancer avec coût", () => {
    usePipelineStore.getState().onEstimateReceived(sampleEstimate);
    render(<EstimateModal />);

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    // Classification rendue en uppercase dans le header.
    expect(screen.getByText("simple")).toBeInTheDocument();
    expect(
      screen.getByText(/Tâche directe : créer un fichier/),
    ).toBeInTheDocument();
    expect(screen.getByText("estimate")).toBeInTheDocument();
    expect(screen.getByText("execute")).toBeInTheDocument();
    expect(screen.getByText(/Lancer.*\$0\.0051/)).toBeInTheDocument();
  });

  it("clic Lancer envoie pipeline_confirmed via ws.send", async () => {
    const { ws } = await import("../ws");
    usePipelineStore.getState().onEstimateReceived(sampleEstimate);
    render(<EstimateModal />);

    fireEvent.click(screen.getByText(/Lancer/));

    expect(ws.send).toHaveBeenCalledWith("pipeline_confirmed", {
      estimate_id: "est-1",
      mode: "simple",
    });
    expect(usePipelineStore.getState().isAwaitingConfirmation).toBe(false);
  });

  it("clic Forcer simple envoie mode=simple", async () => {
    const { ws } = await import("../ws");
    const mediumEstimate: EstimateResult = {
      ...sampleEstimate,
      classification: "medium",
    };
    usePipelineStore.getState().onEstimateReceived(mediumEstimate);
    render(<EstimateModal />);

    fireEvent.click(screen.getByText(/Forcer simple/));

    expect(ws.send).toHaveBeenCalledWith("pipeline_confirmed", {
      estimate_id: "est-1",
      mode: "simple",
    });
  });

  it("clic Annuler reset le store et envoie pipeline_cancelled", async () => {
    const { ws } = await import("../ws");
    usePipelineStore.getState().onEstimateReceived(sampleEstimate);
    render(<EstimateModal />);

    fireEvent.click(screen.getByText("Annuler"));

    expect(ws.send).toHaveBeenCalledWith("pipeline_cancelled", {
      estimate_id: "est-1",
    });
    expect(usePipelineStore.getState().estimate).toBeNull();
    expect(usePipelineStore.getState().isAwaitingConfirmation).toBe(false);
  });
});
