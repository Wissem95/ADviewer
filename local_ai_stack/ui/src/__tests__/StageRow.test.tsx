// Tests StageRow — Plan 5A Task 13.
import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { StageRow } from "../components/Pipeline/StageRow";
import type { StageProgress } from "../types/pipeline";

const baseStage: StageProgress = {
  name: "execute",
  llm: "minimax/minimax-m2.5",
  status: "pending",
  durationMs: 0,
  tokensIn: 0,
  tokensOut: 0,
  costUSD: 0,
  error: null,
};

describe("StageRow", () => {
  it("affiche nom, LLM badge et statut pending", () => {
    render(<StageRow index={0} stage={baseStage} />);
    expect(screen.getByText("execute")).toBeInTheDocument();
    expect(screen.getByText("minimax/minimax-m2.5")).toBeInTheDocument();
    expect(screen.getByLabelText("pending")).toBeInTheDocument();
  });

  it("affiche durée et coût formatés quand done", () => {
    render(
      <StageRow
        index={1}
        stage={{
          ...baseStage,
          status: "done",
          durationMs: 1500,
          costUSD: 0.0123,
        }}
      />,
    );
    expect(screen.getByText("1.5s")).toBeInTheDocument();
    expect(screen.getByText("$0.0123")).toBeInTheDocument();
  });

  it("toggle d'erreur si failed", () => {
    render(
      <StageRow
        index={2}
        stage={{
          ...baseStage,
          status: "failed",
          error: "boom: bad path",
        }}
      />,
    );
    // Erreur cachée par défaut.
    expect(screen.queryByText(/boom: bad path/)).toBeNull();
    fireEvent.click(screen.getByText("Plus"));
    expect(screen.getByText(/boom: bad path/)).toBeInTheDocument();
  });

  it("pas de bouton Plus si pas d'erreur", () => {
    render(
      <StageRow
        index={3}
        stage={{ ...baseStage, status: "done", durationMs: 100 }}
      />,
    );
    expect(screen.queryByText("Plus")).toBeNull();
  });
});
