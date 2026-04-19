import { describe, expect, it } from "vitest";
import { act, render, screen, fireEvent } from "@testing-library/react";
import { FakeWebSocket } from "../test/setup";
import { setupWs } from "../test/wsSetup";

async function setup() {
  const { ws } = await setupWs();
  const ChatTab = (await import("../components/tabs/ChatTab/ChatTab")).default;
  return { ws, ChatTab };
}

describe("ChatTab", () => {
  it("affiche un empty state au démarrage", async () => {
    const { ChatTab } = await setup();
    render(<ChatTab />);
    expect(screen.getByText(/Décris une tâche ou un projet/)).toBeInTheDocument();
  });

  it("envoi : ajoute le message user, émet chat WS, affiche le loader", async () => {
    const { ChatTab } = await setup();
    render(<ChatTab />);
    const sock = FakeWebSocket.instances[0];
    fireEvent.change(screen.getByLabelText("Chat prompt"), { target: { value: "build app" } });
    fireEvent.click(screen.getByLabelText("Send"));

    // Message user affiché
    expect(screen.getByText("build app")).toBeInTheDocument();
    // Event chat émis
    const chat = sock.sent.map((s) => JSON.parse(s)).find((m) => m.type === "chat");
    expect(chat?.data).toEqual({ prompt: "build app", mention: null });
    // Loader visible
    expect(screen.getByTestId("loading")).toBeInTheDocument();
  });

  it("chat_response ajoute le message assistant et retire le loader", async () => {
    const { ChatTab } = await setup();
    render(<ChatTab />);
    const sock = FakeWebSocket.instances[0];
    fireEvent.change(screen.getByLabelText("Chat prompt"), { target: { value: "ping" } });
    fireEvent.click(screen.getByLabelText("Send"));

    act(() =>
      sock._triggerMessage("chat_response", {
        content: "pong",
        llm: "minimax/minimax-m2.5",
        llmName: "MiniMax M2.5",
        tokens: 42,
        durationMs: 800,
      }),
    );

    expect(screen.getByText("pong")).toBeInTheDocument();
    expect(screen.queryByTestId("loading")).toBeNull();
    expect(screen.getByText(/MiniMax M2.5/)).toBeInTheDocument();
    expect(screen.getByText(/0\.8s · 42 tokens/)).toBeInTheDocument();
  });

  it("#2 — 2 prompts concurrents : loader reste tant que les 2 responses ne sont pas arrivées", async () => {
    const { ChatTab } = await setup();
    render(<ChatTab />);
    const sock = FakeWebSocket.instances[0];

    // 1er envoi
    fireEvent.change(screen.getByLabelText("Chat prompt"), { target: { value: "p1" } });
    fireEvent.click(screen.getByLabelText("Send"));
    expect(screen.getByTestId("loading")).toBeInTheDocument();

    // 2e envoi (l'input reste enabled avec pendingCount)
    fireEvent.change(screen.getByLabelText("Chat prompt"), { target: { value: "p2" } });
    fireEvent.click(screen.getByLabelText("Send"));
    const sent = sock.sent.map((s) => JSON.parse(s)).filter((m) => m.type === "chat");
    expect(sent).toHaveLength(2);

    // 1re réponse → pendingCount passe de 2 à 1, loader toujours visible
    act(() =>
      sock._triggerMessage("chat_response", {
        content: "r1",
        llm: "minimax/minimax-m2.5",
        llmName: "MiniMax",
      }),
    );
    expect(screen.getByTestId("loading")).toBeInTheDocument();

    // 2e réponse → pendingCount 1→0, loader disparait
    act(() =>
      sock._triggerMessage("chat_response", {
        content: "r2",
        llm: "minimax/minimax-m2.5",
        llmName: "MiniMax",
      }),
    );
    expect(screen.queryByTestId("loading")).toBeNull();
  });

  it("mention active transmet le LLM choisi dans le payload", async () => {
    const { ChatTab } = await setup();
    render(<ChatTab />);
    const sock = FakeWebSocket.instances[0];
    fireEvent.click(screen.getByRole("button", { name: "@deepseek" }));
    fireEvent.change(screen.getByLabelText("Chat prompt"), { target: { value: "architecture Y" } });
    fireEvent.click(screen.getByLabelText("Send"));
    const chat = sock.sent.map((s) => JSON.parse(s)).find((m) => m.type === "chat");
    expect(chat?.data).toEqual({ prompt: "architecture Y", mention: "deepseek" });
  });
});
