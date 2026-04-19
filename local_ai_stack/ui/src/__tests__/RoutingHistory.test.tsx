import { beforeEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { RoutingHistory } from "../components/tabs/RoutingTab/RoutingHistory";
import { useRoutingStore, type RoutingEntry } from "../stores/routingStore";

const entry = (id: string, overrides: Partial<RoutingEntry> = {}): RoutingEntry => ({
  id,
  timestamp: Date.now(),
  prompt: `prompt-${id}`,
  llm: "minimax/minimax-m2.5",
  role: "coding",
  mode: "medium",
  reason: "complexity=5",
  durationMs: 1800,
  tokens: 250,
  ...overrides,
});

describe("RoutingHistory", () => {
  beforeEach(() => {
    useRoutingStore.setState({ history: [], live: null });
  });

  it("empty state quand aucune entrée", () => {
    render(<RoutingHistory />);
    expect(screen.getByText("Aucune décision enregistrée.")).toBeInTheDocument();
  });

  it("affiche N entrées dans le compteur et dans la table", () => {
    useRoutingStore.setState({
      history: [entry("e1"), entry("e2", { mode: "multi_agent" })],
    });
    render(<RoutingHistory />);
    expect(screen.getByText("Historique (2)")).toBeInTheDocument();
    expect(screen.getByTestId("history-row-e1")).toBeInTheDocument();
    expect(screen.getByTestId("history-row-e2")).toBeInTheDocument();
  });

  it("formate durée (ms → s) et tokens (locale)", () => {
    useRoutingStore.setState({
      history: [entry("e1", { durationMs: 2500, tokens: 1234 })],
    });
    render(<RoutingHistory />);
    const row = screen.getByTestId("history-row-e1");
    expect(row.textContent).toContain("2.5s");
    expect(row.textContent).toContain("1,234");
  });

  it("colore le mode selon le type (multi_agent → error)", () => {
    useRoutingStore.setState({ history: [entry("e1", { mode: "multi_agent" })] });
    render(<RoutingHistory />);
    const modeCell = screen.getByText("multi_agent");
    expect(modeCell.className).toContain("text-error");
  });
});
