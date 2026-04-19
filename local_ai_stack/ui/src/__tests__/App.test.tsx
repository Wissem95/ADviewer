import { describe, expect, it } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import App from "../App";

describe("App layout", () => {
  it("affiche les 4 onglets dans la tab bar", () => {
    render(<App />);
    expect(screen.getByRole("tab", { name: "Chat" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Terminaux" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Routing Flow" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Monitoring" })).toBeInTheDocument();
  });

  it("ChatTab est sélectionné par défaut", () => {
    render(<App />);
    const chat = screen.getByRole("tab", { name: "Chat" });
    expect(chat.getAttribute("aria-selected")).toBe("true");
  });

  it("a11y : tablist a aria-label, tabpanel lié via aria-labelledby", () => {
    render(<App />);
    const tablist = screen.getByRole("tablist");
    expect(tablist.getAttribute("aria-label")).toBe("Vues principales");
    const panel = screen.getByRole("tabpanel");
    expect(panel.getAttribute("aria-labelledby")).toBe("tab-chat");
    expect(panel.id).toBe("tabpanel-chat");
  });

  it("a11y : ArrowRight/ArrowLeft cyclent les onglets et déplacent le focus", () => {
    render(<App />);
    const chatTab = screen.getByRole("tab", { name: "Chat" });
    chatTab.focus();
    act(() => {
      fireEvent.keyDown(chatTab, { key: "ArrowRight" });
    });
    expect(screen.getByRole("tab", { name: "Terminaux" }).getAttribute("aria-selected")).toBe("true");
    // ArrowLeft depuis Chat → dernier onglet (wrap-around)
    const chatAgain = screen.getByRole("tab", { name: "Chat" });
    act(() => fireEvent.click(chatAgain));
    chatAgain.focus();
    act(() => fireEvent.keyDown(chatAgain, { key: "ArrowLeft" }));
    expect(screen.getByRole("tab", { name: "Monitoring" }).getAttribute("aria-selected")).toBe(
      "true",
    );
  });

  it("a11y : tabIndex 0 sur tab actif, -1 sur les autres (roving tabindex)", () => {
    render(<App />);
    expect(screen.getByRole("tab", { name: "Chat" }).getAttribute("tabindex")).toBe("0");
    expect(screen.getByRole("tab", { name: "Terminaux" }).getAttribute("tabindex")).toBe("-1");
  });

  it("cliquer sur un onglet change aria-selected et affiche son contenu", async () => {
    render(<App />);
    fireEvent.click(screen.getByRole("tab", { name: "Monitoring" }));
    expect(screen.getByRole("tab", { name: "Monitoring" }).getAttribute("aria-selected")).toBe(
      "true",
    );
    expect(screen.getByRole("tab", { name: "Chat" }).getAttribute("aria-selected")).toBe("false");
    await waitFor(() => {
      expect(screen.getByTestId("monitoring-grid")).toBeInTheDocument();
    });
  });
});
