import { beforeEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { SprintBoard } from "../components/ActivityBar/SprintBoard";
import { useRoadmapStore } from "../stores/roadmapStore";

const roadmap = {
  project: "demo-app",
  sessionId: "s1",
  tasks: [
    {
      id: "T1",
      title: "Scaffold",
      status: "done" as const,
      assignedTo: "minimax/minimax-m2.5",
      subtasks: [],
      sprint: "Sprint 1",
      estimatedComplexity: 2,
      githubIssue: null,
    },
    {
      id: "T2",
      title: "Auth",
      status: "in_progress" as const,
      assignedTo: "deepseek/deepseek-r1",
      subtasks: [],
      sprint: "Sprint 1",
      estimatedComplexity: 7,
      githubIssue: null,
    },
    {
      id: "T3",
      title: "Billing",
      status: "pending" as const,
      assignedTo: "minimax/minimax-m2.5",
      subtasks: [],
      sprint: "Sprint 2",
      estimatedComplexity: 8,
      githubIssue: null,
    },
  ],
};

describe("SprintBoard", () => {
  beforeEach(() => {
    useRoadmapStore.setState({ roadmap: null });
  });

  it("empty state quand aucune roadmap", () => {
    render(<SprintBoard />);
    expect(screen.getByText("Aucun projet actif.")).toBeInTheDocument();
  });

  it("groupe les tâches par sprint", () => {
    useRoadmapStore.setState({ roadmap });
    render(<SprintBoard />);
    expect(screen.getByTestId("sprint-Sprint 1")).toBeInTheDocument();
    expect(screen.getByTestId("sprint-Sprint 2")).toBeInTheDocument();
    const sprint1 = screen.getByTestId("sprint-Sprint 1");
    expect(sprint1.querySelector("[data-testid='task-T1']")).not.toBeNull();
    expect(sprint1.querySelector("[data-testid='task-T2']")).not.toBeNull();
    expect(sprint1.querySelector("[data-testid='task-T3']")).toBeNull();
  });

  it("affiche l'icône correspondant au status (aria-label)", () => {
    useRoadmapStore.setState({ roadmap });
    render(<SprintBoard />);
    const t1 = screen.getByTestId("task-T1");
    expect(t1.querySelector("[aria-label='done']")).not.toBeNull();
    const t2 = screen.getByTestId("task-T2");
    expect(t2.querySelector("[aria-label='in_progress']")).not.toBeNull();
  });

  it("affiche project + id + score", () => {
    useRoadmapStore.setState({ roadmap });
    render(<SprintBoard />);
    expect(screen.getByText("demo-app")).toBeInTheDocument();
    expect(screen.getByText(/\[T2\].*score 7\/10/)).toBeInTheDocument();
  });
});
