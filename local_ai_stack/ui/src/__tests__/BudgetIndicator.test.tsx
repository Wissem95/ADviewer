// Tests BudgetIndicator — Plan 5B Task 7.
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { BudgetIndicator } from "../components/Pipeline/BudgetIndicator";

describe("BudgetIndicator", () => {
  it("affiche current / cap et le pourcentage", () => {
    render(<BudgetIndicator current={0.05} cap={1.0} />);
    expect(screen.getByText(/\$0\.0500 \/ \$1\.00 \(5%\)/)).toBeInTheDocument();
  });

  it("barre verte sous 50%", () => {
    render(<BudgetIndicator current={0.1} cap={1.0} />);
    const bar = screen.getByRole("progressbar").firstElementChild;
    expect(bar?.className).toMatch(/bg-green-500/);
  });

  it("barre orange entre 50% et 80%", () => {
    render(<BudgetIndicator current={0.6} cap={1.0} />);
    const bar = screen.getByRole("progressbar").firstElementChild;
    expect(bar?.className).toMatch(/bg-orange-500/);
  });

  it("barre rouge à partir de 80%", () => {
    render(<BudgetIndicator current={0.85} cap={1.0} />);
    const bar = screen.getByRole("progressbar").firstElementChild;
    expect(bar?.className).toMatch(/bg-red-500/);
  });

  it("clamp à 100% si current > cap", () => {
    render(<BudgetIndicator current={2.0} cap={1.0} />);
    const progressbar = screen.getByRole("progressbar");
    expect(progressbar.getAttribute("aria-valuenow")).toBe("100");
  });

  it("gère cap=0 sans crasher", () => {
    render(<BudgetIndicator current={0} cap={0} />);
    expect(screen.getByText(/\(0%\)/)).toBeInTheDocument();
  });
});
