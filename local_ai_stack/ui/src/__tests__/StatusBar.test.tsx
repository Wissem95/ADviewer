import { beforeEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusBar } from "../components/StatusBar/StatusBar";
import { useLLMStore } from "../stores/llmStore";
import { useSessionStore } from "../stores/sessionStore";

describe("StatusBar", () => {
  beforeEach(() => {
    useSessionStore.setState({
      branch: "main",
      modifiedFiles: 0,
      tokensToday: 0,
      estimatedCostUSD: 0,
      backendStatus: "connecting",
    });
  });

  it("affiche une pastille par LLM (5 LLMs)", () => {
    render(<StatusBar />);
    expect(screen.getByTestId("status-dot-minimax/minimax-m2.5")).toBeInTheDocument();
    expect(screen.getByTestId("status-dot-gemini/gemini-2.5-pro")).toBeInTheDocument();
    expect(screen.getByTestId("status-dot-gemini/gemini-2.5-flash")).toBeInTheDocument();
    expect(screen.getByTestId("status-dot-deepseek/deepseek-r1")).toBeInTheDocument();
    expect(screen.getByTestId("status-dot-mistral/codestral-2")).toBeInTheDocument();
  });

  it("affiche les modifiés entre parenthèses seulement si > 0", () => {
    const { rerender } = render(<StatusBar />);
    expect(screen.queryByText(/modifiés/)).not.toBeInTheDocument();
    useSessionStore.setState({ branch: "feat/ui", modifiedFiles: 3 });
    rerender(<StatusBar />);
    expect(screen.getByText(/3 modifiés/)).toBeInTheDocument();
  });

  it("formate tokens avec locale et coût à 3 décimales", () => {
    useSessionStore.setState({ tokensToday: 12345, estimatedCostUSD: 0.04567 });
    render(<StatusBar />);
    expect(screen.getByText(/12,345 tokens/)).toBeInTheDocument();
    expect(screen.getByText(/\$0\.046/)).toBeInTheDocument();
  });

  it("affiche l'étiquette backend selon backendStatus", () => {
    useSessionStore.setState({ backendStatus: "connecting" });
    const { rerender } = render(<StatusBar />);
    expect(screen.getByText("Connexion...")).toBeInTheDocument();

    useSessionStore.setState({ backendStatus: "ready" });
    rerender(<StatusBar />);
    expect(screen.getByText("Backend prêt")).toBeInTheDocument();

    useSessionStore.setState({ backendStatus: "error" });
    rerender(<StatusBar />);
    expect(screen.getByText("Backend erreur")).toBeInTheDocument();
  });

  it("pastille LLM busy utilise la couleur warning", () => {
    useLLMStore.getState().setStatus("minimax/minimax-m2.5", "busy", "coding");
    render(<StatusBar />);
    const dot = screen.getByTestId("status-dot-minimax/minimax-m2.5");
    expect(dot.className).toContain("bg-warning");
    useLLMStore.getState().setStatus("minimax/minimax-m2.5", "idle");
  });
});
