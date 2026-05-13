// Tests PlanDiffView — Plan 5C Task 4.
import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, act } from "@testing-library/react";
import { PlanDiffView } from "../components/Pipeline/PlanDiffView";
import { usePipelineStore } from "../stores/pipelineStore";
import type { PlanResultPayload } from "../types/pipeline";

vi.mock("../ws", () => ({
  ws: {
    on: vi.fn(() => () => undefined),
    send: vi.fn(),
  },
}));

const sample: PlanResultPayload = {
  changes: [
    {
      file: "backend/auth.py",
      operation: "patch",
      description: "Use create_token helper",
      intendedDiffSummary: "swap encode call",
    },
    {
      file: "backend/auth_jwt.py",
      operation: "create",
      description: "New JWT helper module",
      intendedDiffSummary: "",
    },
  ],
  testsToRun: ["tests/backend/test_auth.py::test_login"],
  rollbackStrategy: "git stash pop",
  rationale: "auth.py:42 calls jwt.encode directly (vu en GROUND)",
  estimatedRisk: "medium",
  complexityConfirm: 5,
};

describe("PlanDiffView", () => {
  afterEach(() => {
    usePipelineStore.getState().reset();
    vi.clearAllMocks();
  });

  it("ne render rien si plan null", () => {
    render(<PlanDiffView />);
    expect(screen.queryByTestId("plan-diff-view")).toBeNull();
  });

  it("affiche changes avec icônes operation + risk badge", () => {
    act(() => usePipelineStore.getState().onPlanResult(sample));
    render(<PlanDiffView />);
    expect(screen.getByTestId("plan-diff-view")).toBeInTheDocument();
    expect(screen.getByTestId("plan-change-0")).toBeInTheDocument();
    expect(screen.getByTestId("plan-change-1")).toBeInTheDocument();
    expect(screen.getByText("backend/auth.py")).toBeInTheDocument();
    expect(screen.getByText(/risque medium/)).toBeInTheDocument();
  });

  it("affiche tests_to_run et rationale", () => {
    act(() => usePipelineStore.getState().onPlanResult(sample));
    render(<PlanDiffView />);
    expect(
      screen.getByText("tests/backend/test_auth.py::test_login"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("plan-rationale")).toBeInTheDocument();
    expect(screen.getByText(/auth\.py:42/)).toBeInTheDocument();
  });

  it("affiche '2 changes' avec pluriel", () => {
    act(() => usePipelineStore.getState().onPlanResult(sample));
    render(<PlanDiffView />);
    expect(screen.getByText(/2 changes/)).toBeInTheDocument();
  });

  it("collapse via le bouton header", () => {
    act(() => usePipelineStore.getState().onPlanResult(sample));
    render(<PlanDiffView />);
    expect(screen.getByText("backend/auth.py")).toBeInTheDocument();
    fireEvent.click(screen.getByText(/Plan/));
    expect(screen.queryByText("backend/auth.py")).toBeNull();
  });

  it("risque high → badge rouge", () => {
    act(() =>
      usePipelineStore.getState().onPlanResult({
        ...sample,
        estimatedRisk: "high",
      }),
    );
    render(<PlanDiffView />);
    const badge = screen.getByTestId("plan-risk-badge");
    expect(badge.className).toMatch(/bg-red-/);
  });
});
