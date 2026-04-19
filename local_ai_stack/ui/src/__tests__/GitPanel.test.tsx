import { describe, expect, it, vi } from "vitest";
import { act, render, screen, fireEvent } from "@testing-library/react";
import { FakeWebSocket } from "../test/setup";
import type { GitFile } from "../components/ActivityBar/GitPanel";

const sampleFiles: GitFile[] = [
  { path: "src/main.ts", status: "modified" },
  { path: "src/new.ts", status: "added" },
  { path: "README.md", status: "untracked" },
];

async function setup() {
  vi.resetModules();
  FakeWebSocket.instances = [];
  const { ws } = await import("../ws");
  ws.connect();
  const { GitPanel } = await import("../components/ActivityBar/GitPanel");
  FakeWebSocket.instances[0]._triggerOpen();
  return { ws, GitPanel };
}

describe("GitPanel", () => {
  it("demande la diff git au montage et hydrate l'état sur git_diff_files", async () => {
    const { GitPanel } = await setup();
    render(<GitPanel />);
    const sock = FakeWebSocket.instances[0];
    expect(sock.sent.some((s) => JSON.parse(s).type === "request_git_diff")).toBe(true);
    act(() => sock._triggerMessage("git_diff_files", sampleFiles));
    expect(screen.getByTestId("git-file-src/main.ts")).toBeInTheDocument();
    expect(screen.getByTestId("git-file-src/new.ts")).toBeInTheDocument();
  });

  it("toggleStage sur checkbox met à jour le compteur", async () => {
    const { GitPanel } = await setup();
    render(<GitPanel />);
    act(() => FakeWebSocket.instances[0]._triggerMessage("git_diff_files", sampleFiles));
    const row = screen.getByTestId("git-file-src/main.ts");
    const cb = row.querySelector("input[type=checkbox]") as HTMLInputElement;
    fireEvent.click(cb);
    expect(screen.getByText(/Commit \(1\)/)).toBeInTheDocument();
    fireEvent.click(cb);
    expect(screen.getByText(/Commit \(0\)/)).toBeInTheDocument();
  });

  it("bouton commit disabled tant que (msg vide OR aucun staged)", async () => {
    const { GitPanel } = await setup();
    render(<GitPanel />);
    act(() => FakeWebSocket.instances[0]._triggerMessage("git_diff_files", sampleFiles));
    const btn = screen.getByRole("button", { name: /Commit/ });
    expect(btn).toBeDisabled();

    const row = screen.getByTestId("git-file-src/main.ts");
    fireEvent.click(row.querySelector("input[type=checkbox]")!);
    expect(btn).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Commit message"), { target: { value: "fix: x" } });
    expect(btn).not.toBeDisabled();
  });

  it("commit émet git_commit puis reset msg et staged", async () => {
    const { GitPanel } = await setup();
    render(<GitPanel />);
    const sock = FakeWebSocket.instances[0];
    act(() => sock._triggerMessage("git_diff_files", sampleFiles));

    fireEvent.click(
      screen.getByTestId("git-file-src/main.ts").querySelector("input[type=checkbox]")!,
    );
    fireEvent.change(screen.getByLabelText("Commit message"), { target: { value: "fix: bug" } });
    fireEvent.click(screen.getByRole("button", { name: /Commit/ }));

    const commits = sock.sent.map((s) => JSON.parse(s)).filter((m) => m.type === "git_commit");
    expect(commits).toHaveLength(1);
    expect(commits[0].data).toEqual({ files: ["src/main.ts"], message: "fix: bug" });

    expect((screen.getByLabelText("Commit message") as HTMLInputElement).value).toBe("");
    expect(screen.getByText(/Commit \(0\)/)).toBeInTheDocument();
  });

  it("affiche 'Aucun changement' si la liste est vide", async () => {
    const { GitPanel } = await setup();
    render(<GitPanel />);
    act(() => FakeWebSocket.instances[0]._triggerMessage("git_diff_files", []));
    expect(screen.getByText("Aucun changement")).toBeInTheDocument();
  });
});
