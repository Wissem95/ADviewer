// Tests ChallengePanel — Plan 5C Task 2.
import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, act } from "@testing-library/react";
import { ChallengePanel } from "../components/Pipeline/ChallengePanel";
import { usePipelineStore } from "../stores/pipelineStore";
import type { ChallengeResultPayload } from "../types/pipeline";

vi.mock("../ws", () => ({
  ws: {
    on: vi.fn(() => () => undefined),
    send: vi.fn(),
  },
}));

const sample: ChallengeResultPayload = {
  risks: ["Risque numéro un précis", "Risque numéro deux"],
  edgeCases: ["Cas limite A"],
  alternatives: ["Alternative B"],
  severity: "moderate",
  blocking: false,
};

describe("ChallengePanel", () => {
  afterEach(() => {
    usePipelineStore.getState().reset();
    vi.clearAllMocks();
  });

  it("ne render rien si challenge null", () => {
    render(<ChallengePanel />);
    expect(screen.queryByTestId("challenge-panel")).toBeNull();
  });

  it("affiche risks/edge_cases/alternatives + severity badge", () => {
    act(() => usePipelineStore.getState().onChallengeResult(sample));
    render(<ChallengePanel />);
    expect(screen.getByTestId("challenge-panel")).toBeInTheDocument();
    expect(screen.getByText("Risque numéro un précis")).toBeInTheDocument();
    expect(screen.getByText("Cas limite A")).toBeInTheDocument();
    expect(screen.getByText("Alternative B")).toBeInTheDocument();
    expect(screen.getByText("moderate")).toBeInTheDocument();
  });

  it("affiche banner blocking si challengeBlocking=true", () => {
    act(() => {
      usePipelineStore.getState().onChallengeResult({
        ...sample,
        severity: "critical",
        blocking: true,
      });
      usePipelineStore.getState().onChallengeBlocking({
        severity: "critical",
        risks: ["x"],
      });
    });
    render(<ChallengePanel />);
    expect(screen.getByTestId("challenge-blocking-banner")).toBeInTheDocument();
    expect(screen.getByText("Continuer")).toBeInTheDocument();
    expect(screen.getByText("Annuler")).toBeInTheDocument();
  });

  it("clic Continuer acknowledge et cache le banner", () => {
    act(() => {
      usePipelineStore.getState().onChallengeResult({
        ...sample,
        blocking: true,
      });
      usePipelineStore.getState().onChallengeBlocking({
        severity: "critical",
        risks: ["x"],
      });
    });
    render(<ChallengePanel />);
    fireEvent.click(screen.getByText("Continuer"));
    expect(usePipelineStore.getState().challengeBlocking).toBe(false);
  });

  it("clic Annuler envoie pipeline_stop", async () => {
    const { ws } = await import("../ws");
    act(() => {
      usePipelineStore.getState().onChallengeResult({
        ...sample,
        blocking: true,
      });
      usePipelineStore.getState().onChallengeBlocking({
        severity: "critical",
        risks: ["x"],
      });
    });
    render(<ChallengePanel />);
    fireEvent.click(screen.getByText("Annuler"));
    expect(ws.send).toHaveBeenCalledWith("pipeline_stop", {
      reason: "challenge-blocking",
    });
  });

  it("collapse/expand via le bouton header", () => {
    act(() => usePipelineStore.getState().onChallengeResult(sample));
    render(<ChallengePanel />);
    expect(screen.getByText("Risque numéro un précis")).toBeInTheDocument();
    fireEvent.click(screen.getByText(/Challenge/));
    expect(screen.queryByText("Risque numéro un précis")).toBeNull();
  });
});
