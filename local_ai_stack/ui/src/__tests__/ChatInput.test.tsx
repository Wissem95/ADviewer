import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ChatInput } from "../components/tabs/ChatTab/ChatInput";

describe("ChatInput", () => {
  it("bouton send disabled si prompt vide", () => {
    render(<ChatInput onSend={vi.fn()} />);
    expect(screen.getByLabelText("Send")).toBeDisabled();
  });

  it("saisie active le bouton et appelle onSend", () => {
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} />);
    fireEvent.change(screen.getByLabelText("Chat prompt"), { target: { value: "hello" } });
    const send = screen.getByLabelText("Send");
    expect(send).not.toBeDisabled();
    fireEvent.click(send);
    expect(onSend).toHaveBeenCalledWith("hello", null);
  });

  it("Enter envoie ; Shift+Enter insère une newline (n'envoie pas)", () => {
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} />);
    const ta = screen.getByLabelText("Chat prompt");
    fireEvent.change(ta, { target: { value: "foo" } });
    fireEvent.keyDown(ta, { key: "Enter", shiftKey: true });
    expect(onSend).not.toHaveBeenCalled();
    fireEvent.keyDown(ta, { key: "Enter" });
    expect(onSend).toHaveBeenCalledWith("foo", null);
  });

  it("toggle @mention met à jour activeMention (clique deux fois = off)", () => {
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} />);
    const mentionBtn = screen.getByRole("button", { name: "@minimax" });
    fireEvent.click(mentionBtn);
    expect(mentionBtn.getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByTestId("routing-label").textContent).toContain("minimax");

    fireEvent.change(screen.getByLabelText("Chat prompt"), { target: { value: "fix" } });
    fireEvent.click(screen.getByLabelText("Send"));
    expect(onSend).toHaveBeenCalledWith("fix", "minimax");

    // Après send, mention reset + label revient à "Auto-routing"
    expect(screen.getByTestId("routing-label").textContent).toBe("Auto-routing");
    expect(mentionBtn.getAttribute("aria-pressed")).toBe("false");
  });

  it("disabled bloque onSend même si textarea a du contenu", () => {
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} disabled />);
    const ta = screen.getByLabelText("Chat prompt");
    fireEvent.change(ta, { target: { value: "x" } });
    fireEvent.keyDown(ta, { key: "Enter" });
    expect(onSend).not.toHaveBeenCalled();
  });
});
