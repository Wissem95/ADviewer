import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { DEFAULT_LLMS, useLLMStore } from "../stores/llmStore";

// Mock xterm pour éviter le coût de chargement réel en jsdom.
const writeLogs: string[] = [];
vi.mock("@xterm/xterm", () => ({
  Terminal: class {
    loadAddon() {}
    open() {}
    writeln(line: string) {
      writeLogs.push(line);
    }
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
    writeLogs.length = 0;
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

  it("#1 — lignes agent_log reçues pendant l'init xterm sont bufferisées puis flushées", async () => {
    // Active un seul LLM
    const state = DEFAULT_LLMS.map((l, i) => ({
      ...l,
      status: i === 0 ? ("idle" as const) : ("disabled" as const),
    }));
    useLLMStore.setState({ llms: state });

    const { ws } = await import("../ws");
    ws.connect();
    // Simule une ligne agent_log arrivée AVANT la résolution du dynamic import
    // (le handler ws.on s'inscrit synchronement au montage, mais termRef.current
    // n'existe qu'après l'await Promise.all). Le FakeWebSocket déclenche le
    // message tout de suite, puis on attend que l'async import se résolve.
    const sock = (await import("../test/setup")).FakeWebSocket.instances[0];

    render(<TerminalsTab />);
    sock._triggerOpen();
    // La ligne arrive IMMÉDIATEMENT — avant que Promise.all d'import n'ait résolu
    sock._triggerMessage("agent_log", { llm: DEFAULT_LLMS[0].id, line: "LINE_EARLY" });

    // Laisse le microtask queue drainer pour que l'import dynamique se résolve
    await new Promise((r) => setTimeout(r, 0));
    await new Promise((r) => setTimeout(r, 0));

    // Ligne reçue tardivement (après init)
    sock._triggerMessage("agent_log", { llm: DEFAULT_LLMS[0].id, line: "LINE_LATE" });

    // Les 2 lignes doivent apparaître dans writeLogs (early bufferisée puis flushée, late directe)
    expect(writeLogs).toContain("LINE_EARLY");
    expect(writeLogs).toContain("LINE_LATE");
  });
});
