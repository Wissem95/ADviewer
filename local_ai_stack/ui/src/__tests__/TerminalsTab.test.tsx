import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { DEFAULT_LLMS, useLLMStore } from "../stores/llmStore";

// Mock xterm pour éviter le coût de chargement réel en jsdom.
vi.mock("@xterm/xterm", () => ({
  Terminal: class {
    loadAddon() {}
    open() {}
    writeln() {}
    dispose() {}
  },
}));
vi.mock("@xterm/addon-fit", () => ({
  FitAddon: class {
    fit() {}
  },
}));

import TerminalsTab from "../components/tabs/TerminalsTab/TerminalsTab";

describe("TerminalsTab", () => {
  beforeEach(() => {
    useLLMStore.setState({ llms: DEFAULT_LLMS.map((l) => ({ ...l })) });
  });

  it("empty state si tous les LLMs sont disabled", () => {
    useLLMStore.setState({
      llms: DEFAULT_LLMS.map((l) => ({ ...l, status: "disabled" as const })),
    });
    render(<TerminalsTab />);
    expect(screen.getByText("Aucun LLM actif.")).toBeInTheDocument();
  });

  it("1 terminal par LLM actif (5 par défaut)", () => {
    render(<TerminalsTab />);
    for (const llm of DEFAULT_LLMS) {
      expect(screen.getByTestId(`terminal-${llm.id}`)).toBeInTheDocument();
    }
  });

  it("grid 1 colonne si 1 seul LLM actif", () => {
    const state = DEFAULT_LLMS.map((l, i) => ({
      ...l,
      status: i === 0 ? ("idle" as const) : ("disabled" as const),
    }));
    useLLMStore.setState({ llms: state });
    render(<TerminalsTab />);
    const grid = screen.getByTestId("terminals-grid");
    expect(grid.className).toContain("grid-cols-1");
  });

  it("grid 2 colonnes si plusieurs LLMs actifs", () => {
    render(<TerminalsTab />);
    const grid = screen.getByTestId("terminals-grid");
    expect(grid.className).toContain("grid-cols-2");
  });
});
