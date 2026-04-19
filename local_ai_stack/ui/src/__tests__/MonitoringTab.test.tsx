import { describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";
import { FakeWebSocket } from "../test/setup";

async function setup() {
  vi.resetModules();
  FakeWebSocket.instances = [];
  const { ws } = await import("../ws");
  ws.connect();
  const MonitoringTab = (await import("../components/tabs/MonitoringTab/MonitoringTab")).default;
  FakeWebSocket.instances[0]._triggerOpen();
  return { ws, MonitoringTab };
}

describe("MonitoringTab", () => {
  it("demande les sys_stats au montage", async () => {
    const { MonitoringTab } = await setup();
    render(<MonitoringTab />);
    const sock = FakeWebSocket.instances[0];
    expect(sock.sent.some((s) => JSON.parse(s).type === "request_sys_stats")).toBe(true);
  });

  it("hydrate CPU/RAM via sys_stats", async () => {
    const { MonitoringTab } = await setup();
    render(<MonitoringTab />);
    const sock = FakeWebSocket.instances[0];
    act(() => sock._triggerMessage("sys_stats", { cpuPercent: 34.7, ramMB: 512 }));
    expect(screen.getByTestId("cpu").textContent).toBe("34.7%");
    expect(screen.getByTestId("ram").textContent).toBe("512 MB");
  });

  it("ajoute/update un CI status par ticketId", async () => {
    const { MonitoringTab } = await setup();
    render(<MonitoringTab />);
    const sock = FakeWebSocket.instances[0];
    // Ajout
    act(() =>
      sock._triggerMessage("ci_status", { ticketId: "T1", status: "running", url: "" }),
    );
    expect(screen.getByTestId("ci-T1").textContent).toContain("T1");
    expect(screen.getByTestId("ci-T1").textContent).toContain("🔄");
    // Update même ticketId → status success (pas de doublon)
    act(() =>
      sock._triggerMessage("ci_status", { ticketId: "T1", status: "success", url: "" }),
    );
    const rows = screen.getAllByTestId("ci-T1");
    expect(rows).toHaveLength(1);
    expect(rows[0].textContent).toContain("✅");
  });

  it("sys_stats payload corrompu : valeurs défensives 0", async () => {
    const { MonitoringTab } = await setup();
    render(<MonitoringTab />);
    const sock = FakeWebSocket.instances[0];
    // Payload partiel : cpuPercent null, ramMB manquant
    act(() => sock._triggerMessage("sys_stats", { cpuPercent: null, ramMB: undefined }));
    expect(screen.getByTestId("cpu").textContent).toBe("0.0%");
    expect(screen.getByTestId("ram").textContent).toBe("0 MB");
  });

  it("empty state CI par défaut", async () => {
    const { MonitoringTab } = await setup();
    render(<MonitoringTab />);
    expect(screen.getByText("Aucun CI en cours.")).toBeInTheDocument();
  });
});
