// Tests DeadlockModal — Plan 5C Task 7.
import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, act } from "@testing-library/react";
import { DeadlockModal } from "../components/Pipeline/DeadlockModal";
import { usePipelineStore } from "../stores/pipelineStore";
import type { DeadlockPayload } from "../types/pipeline";

vi.mock("../ws", () => ({
  ws: {
    on: vi.fn(() => () => undefined),
    send: vi.fn(),
  },
}));

const sample: DeadlockPayload = {
  plans: [
    {
      changes: [
        {
          file: "auth.py",
          operation: "patch",
          description: "Plan A",
          intendedDiffSummary: "",
        },
      ],
      testsToRun: ["tests/auth.py::test_a"],
      rollbackStrategy: "stash",
      rationale: "r1",
      estimatedRisk: "low",
      complexityConfirm: 3,
    },
    {
      changes: [
        {
          file: "auth.py",
          operation: "patch",
          description: "Plan B",
          intendedDiffSummary: "",
        },
        {
          file: "helper.py",
          operation: "create",
          description: "new helper",
          intendedDiffSummary: "",
        },
      ],
      testsToRun: ["tests/auth.py::test_b", "tests/helper.py::test_h"],
      rollbackStrategy: "stash",
      rationale: "r2",
      estimatedRisk: "medium",
      complexityConfirm: 5,
    },
  ],
  concerns: [["concern A1"], ["concern B1", "concern B2"]],
};

describe("DeadlockModal", () => {
  afterEach(() => {
    usePipelineStore.getState().reset();
    vi.clearAllMocks();
  });

  it("ne render rien si deadlock null", () => {
    render(<DeadlockModal />);
    expect(screen.queryByTestId("deadlock-modal")).toBeNull();
  });

  it("affiche les 2 plans côte-à-côte avec concerns", () => {
    act(() => usePipelineStore.getState().onDeadlock(sample));
    render(<DeadlockModal />);
    expect(screen.getByTestId("deadlock-modal")).toBeInTheDocument();
    expect(screen.getByTestId("plan-card-Plan A")).toBeInTheDocument();
    expect(screen.getByTestId("plan-card-Plan B")).toBeInTheDocument();
    expect(screen.getByText(/concern A1/)).toBeInTheDocument();
    expect(screen.getByText(/concern B2/)).toBeInTheDocument();
  });

  it("clic 'Utiliser ce plan' (Plan A) envoie user_decision plan1", async () => {
    const { ws } = await import("../ws");
    act(() => usePipelineStore.getState().onDeadlock(sample));
    render(<DeadlockModal />);

    const buttons = screen.getAllByText("Utiliser ce plan");
    fireEvent.click(buttons[0]);

    expect(ws.send).toHaveBeenCalledWith(
      "user_decision",
      expect.objectContaining({ type: "plan_deadlock", choice: "plan1" }),
    );
    expect(usePipelineStore.getState().deadlock).toBeNull();
  });

  it("clic 'Utiliser ce plan' (Plan B) envoie plan2", async () => {
    const { ws } = await import("../ws");
    act(() => usePipelineStore.getState().onDeadlock(sample));
    render(<DeadlockModal />);

    const buttons = screen.getAllByText("Utiliser ce plan");
    fireEvent.click(buttons[1]);

    expect(ws.send).toHaveBeenCalledWith(
      "user_decision",
      expect.objectContaining({ choice: "plan2" }),
    );
  });

  it("clic Annuler envoie user_decision cancel + pipeline_stop", async () => {
    const { ws } = await import("../ws");
    act(() => usePipelineStore.getState().onDeadlock(sample));
    render(<DeadlockModal />);

    fireEvent.click(screen.getByText("Annuler le pipeline"));

    expect(ws.send).toHaveBeenCalledWith(
      "user_decision",
      expect.objectContaining({ choice: "cancel" }),
    );
    expect(ws.send).toHaveBeenCalledWith("pipeline_stop", {
      reason: "deadlock-cancelled",
    });
  });

  it("résolution efface le deadlock du store", () => {
    act(() => usePipelineStore.getState().onDeadlock(sample));
    expect(usePipelineStore.getState().deadlock).not.toBeNull();
    act(() => usePipelineStore.getState().resolveDeadlock("plan1"));
    expect(usePipelineStore.getState().deadlock).toBeNull();
  });
});
