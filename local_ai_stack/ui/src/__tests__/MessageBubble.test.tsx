import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MessageBubble, type Message } from "../components/tabs/ChatTab/MessageBubble";

const baseUserMsg: Message = {
  id: "u1",
  role: "user",
  content: "Salut",
  timestamp: 0,
};

const assistantMsg: Message = {
  id: "a1",
  role: "assistant",
  content: "Bonjour",
  llm: "minimax/minimax-m2.5",
  llmName: "MiniMax M2.5",
  tokens: 123,
  durationMs: 1500,
  timestamp: 0,
};

describe("MessageBubble", () => {
  it("message user : alignement droite, pas de badge LLM", () => {
    render(<MessageBubble message={baseUserMsg} />);
    expect(screen.getByText("Salut")).toBeInTheDocument();
    expect(screen.queryByTestId("badge-u1")).toBeNull();
  });

  it("message assistant avec llmName : badge + couleur du LLM + formatage durée/tokens", () => {
    render(<MessageBubble message={assistantMsg} />);
    const badge = screen.getByTestId("badge-a1");
    expect(badge.textContent).toContain("MiniMax M2.5");
    expect(badge.textContent).toContain("💻");
    expect(badge.className).toContain("bg-accent");
    // 1500ms -> 1.5s · 123 tokens
    expect(screen.getByText(/1\.5s · 123 tokens/)).toBeInTheDocument();
  });

  it("message assistant LLM inconnu : fallback robot + classe muted", () => {
    render(
      <MessageBubble
        message={{ ...assistantMsg, llm: "unknown/xxx", llmName: "Unknown" }}
      />,
    );
    const badge = screen.getByTestId("badge-a1");
    expect(badge.textContent).toContain("🤖");
    expect(badge.className).toContain("bg-muted");
  });
});
