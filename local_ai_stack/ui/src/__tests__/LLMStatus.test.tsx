import { beforeEach, describe, expect, it } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { LLMStatus } from "../components/ActivityBar/LLMStatus";
import { DEFAULT_LLMS, useLLMStore } from "../stores/llmStore";

describe("LLMStatus", () => {
  beforeEach(() => {
    // Reset store aux 5 LLMs par défaut (deep copy pour éviter mutation entre tests)
    useLLMStore.setState({
      llms: DEFAULT_LLMS.map((l) => ({ ...l })),
    });
  });

  it("affiche une carte par LLM", () => {
    render(<LLMStatus />);
    for (const llm of DEFAULT_LLMS) {
      expect(screen.getByTestId(`llm-card-${llm.id}`)).toBeInTheDocument();
    }
  });

  it("busy masque le bouton désactiver et affiche la task courante", () => {
    useLLMStore.getState().setStatus("minimax/minimax-m2.5", "busy", "refactor payment");
    render(<LLMStatus />);
    const card = screen.getByTestId("llm-card-minimax/minimax-m2.5");
    expect(card.textContent).toContain("refactor payment");
    expect(card.querySelector("button")).toBeNull();
  });

  it("toggle disabled via bouton", () => {
    render(<LLMStatus />);
    const card = screen.getByTestId("llm-card-gemini/gemini-2.5-pro");
    const btn = card.querySelector("button")!;
    expect(btn.textContent).toBe("Désact.");
    fireEvent.click(btn);
    expect(
      useLLMStore.getState().llms.find((l) => l.id === "gemini/gemini-2.5-pro")?.status,
    ).toBe("disabled");
    // Le bouton passe à "Activer"
    expect(screen.getByTestId("llm-card-gemini/gemini-2.5-pro").querySelector("button")!.textContent).toBe(
      "Activer",
    );
  });

  it("status error : affiche un bouton Reset qui remet en idle", () => {
    useLLMStore.getState().setStatus("minimax/minimax-m2.5", "error");
    render(<LLMStatus />);
    const card = screen.getByTestId("llm-card-minimax/minimax-m2.5");
    const btn = card.querySelector("button")!;
    expect(btn.textContent).toBe("Reset");
    fireEvent.click(btn);
    expect(
      useLLMStore.getState().llms.find((l) => l.id === "minimax/minimax-m2.5")?.status,
    ).toBe("idle");
  });

  it("affiche tokens et latency formatés", () => {
    useLLMStore.getState().updateTokens("deepseek/deepseek-r1", 1250);
    useLLMStore.getState().updateLatency("deepseek/deepseek-r1", 423);
    render(<LLMStatus />);
    const card = screen.getByTestId("llm-card-deepseek/deepseek-r1");
    expect(card.textContent).toMatch(/1,250 tokens/);
    expect(card.textContent).toMatch(/423ms/);
  });
});
