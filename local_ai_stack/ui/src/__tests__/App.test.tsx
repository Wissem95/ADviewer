import { describe, expect, it } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
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
