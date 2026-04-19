import { describe, expect, it } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ActivityBar } from "../components/ActivityBar/ActivityBar";

describe("ActivityBar", () => {
  it("affiche 4 boutons de navigation (files, llms, git, sprints)", () => {
    render(<ActivityBar />);
    expect(screen.getByTitle("files")).toBeInTheDocument();
    expect(screen.getByTitle("llms")).toBeInTheDocument();
    expect(screen.getByTitle("git")).toBeInTheDocument();
    expect(screen.getByTitle("sprints")).toBeInTheDocument();
  });

  it("FileTree est le panneau par défaut", () => {
    render(<ActivityBar />);
    expect(screen.getByTestId("panel-files")).toBeInTheDocument();
    expect(screen.getByTitle("files").getAttribute("aria-pressed")).toBe("true");
  });

  it("cliquer sur une icône change le panneau actif", () => {
    render(<ActivityBar />);
    fireEvent.click(screen.getByTitle("llms"));
    expect(screen.getByTestId("panel-llms")).toBeInTheDocument();
    expect(screen.getByTitle("llms").getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByTitle("files").getAttribute("aria-pressed")).toBe("false");
  });
});
