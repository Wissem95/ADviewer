// Tests ConsensusRoundsLog — Plan 5C Task 9.
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { ConsensusRoundsLog } from "../components/Pipeline/ConsensusRoundsLog";
import { usePipelineStore } from "../stores/pipelineStore";
import type { ConsensusRound } from "../types/pipeline";

vi.mock("../ws", () => ({
  ws: {
    on: vi.fn(() => () => undefined),
    send: vi.fn(),
  },
}));

const round1: ConsensusRound = {
  round: 1,
  verdict: "reject",
  planSummary: { changes_count: 3, tests_count: 2, estimated_risk: "medium" },
  concerns: ["missing edge case", "no rollback"],
};

const round2: ConsensusRound = {
  round: 2,
  verdict: "approve",
  planSummary: { changes_count: 4, tests_count: 3, estimated_risk: "low" },
  concerns: [],
};

describe("ConsensusRoundsLog", () => {
  afterEach(() => {
    usePipelineStore.getState().reset();
    vi.clearAllMocks();
  });

  it("ne render rien si aucun round", () => {
    render(<ConsensusRoundsLog />);
    expect(screen.queryByTestId("consensus-rounds-log")).toBeNull();
  });

  it("affiche un round unique avec verdict et concerns", () => {
    act(() => usePipelineStore.getState().onConsensusRound(round1));
    render(<ConsensusRoundsLog />);
    expect(screen.getByTestId("consensus-rounds-log")).toBeInTheDocument();
    expect(screen.getByTestId("consensus-round-1")).toBeInTheDocument();
    expect(screen.getByText("reject")).toBeInTheDocument();
    expect(screen.getByText(/missing edge case/)).toBeInTheDocument();
    expect(screen.getByText(/1 round\b/)).toBeInTheDocument();
  });

  it("accumule plusieurs rounds dans l'ordre", () => {
    const store = usePipelineStore.getState();
    act(() => {
      store.onConsensusRound(round1);
      store.onConsensusRound(round2);
    });
    render(<ConsensusRoundsLog />);
    expect(screen.getByTestId("consensus-round-1")).toBeInTheDocument();
    expect(screen.getByTestId("consensus-round-2")).toBeInTheDocument();
    expect(screen.getByText(/2 rounds/)).toBeInTheDocument();
    expect(screen.getByText("approve")).toBeInTheDocument();
  });

  it("résumé plan affiche pluriels corrects", () => {
    act(() => usePipelineStore.getState().onConsensusRound(round1));
    render(<ConsensusRoundsLog />);
    // 3 changes, 2 tests → pluriels
    expect(screen.getByText(/3 changes · 2 tests · risque medium/)).toBeInTheDocument();
  });

  it("verdict revise → badge orange", () => {
    act(() =>
      usePipelineStore.getState().onConsensusRound({
        ...round1,
        verdict: "revise",
      }),
    );
    render(<ConsensusRoundsLog />);
    const badge = screen.getByText("revise");
    expect(badge.className).toMatch(/bg-orange-/);
  });

  it("rounds sans concerns n'affichent pas de bullets", () => {
    act(() => usePipelineStore.getState().onConsensusRound(round2));
    const { container } = render(<ConsensusRoundsLog />);
    // Pas de ul.list-disc dans le round 2 (concerns vide).
    expect(container.querySelector("ul.list-disc")).toBeNull();
  });
});
