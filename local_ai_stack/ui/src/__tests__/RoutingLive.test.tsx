import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { RoutingLive } from "../components/tabs/RoutingTab/RoutingLive";
import { useRoutingStore } from "../stores/routingStore";

describe("RoutingLive", () => {
  beforeEach(() => {
    useRoutingStore.setState({ history: [], live: null });
  });

  it("empty state quand pas de routage en cours", () => {
    render(<RoutingLive />);
    expect(screen.getByText("Aucune tâche en cours.")).toBeInTheDocument();
  });

  it("pipeline : marque steps < active comme done et step actif pulsant", () => {
    useRoutingStore.setState({
      live: { prompt: "fix bug", llm: "minimax/minimax-m2.5", step: "EXECUTE", attempt: 1 },
    });
    render(<RoutingLive />);
    expect(screen.getByTestId("step-PLAN").dataset.state).toBe("done");
    expect(screen.getByTestId("step-VERIFY").dataset.state).toBe("done");
    expect(screen.getByTestId("step-EXECUTE").dataset.state).toBe("active");
    expect(screen.getByTestId("step-CHECK").dataset.state).toBe("pending");
    expect(screen.getByTestId("step-CONFIRM").dataset.state).toBe("pending");
  });

  it("affiche le nom court du LLM (dernier segment)", () => {
    useRoutingStore.setState({
      live: { prompt: "p", llm: "gemini/gemini-2.5-pro", step: "PLAN", attempt: 1 },
    });
    render(<RoutingLive />);
    expect(screen.getByText("gemini-2.5-pro")).toBeInTheDocument();
  });

  it("step inconnue : console.warn + tous les steps en pending", () => {
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    useRoutingStore.setState({
      live: { prompt: "p", llm: "minimax/minimax-m2.5", step: "UNKNOWN_STEP", attempt: 1 },
    });
    render(<RoutingLive />);
    expect(warnSpy).toHaveBeenCalledWith(
      expect.stringContaining("step inconnue"),
      "UNKNOWN_STEP",
    );
    expect(screen.getByTestId("step-PLAN").dataset.state).toBe("pending");
    expect(screen.getByTestId("step-CONFIRM").dataset.state).toBe("pending");
    warnSpy.mockRestore();
  });

  it("indique la tentative quand attempt > 1", () => {
    useRoutingStore.setState({
      live: { prompt: "p", llm: "minimax/minimax-m2.5", step: "PLAN", attempt: 2 },
    });
    render(<RoutingLive />);
    expect(screen.getByText(/Tentative 2\/3/)).toBeInTheDocument();
  });
});
