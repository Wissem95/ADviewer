import { describe, expect, it, vi } from "vitest";
import { act, render, screen, fireEvent } from "@testing-library/react";
import { FakeWebSocket } from "../test/setup";

async function setup() {
  vi.resetModules();
  FakeWebSocket.instances = [];
  const { ws } = await import("../ws");
  ws.connect();
  const ChatTab = (await import("../components/tabs/ChatTab/ChatTab")).default;
  FakeWebSocket.instances[0]._triggerOpen();
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
