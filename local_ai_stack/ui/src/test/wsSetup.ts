// Helper test : réinitialise le module graph, importe ws.ts frais,
// connecte + _triggerOpen() la FakeWebSocket. Retourne ws + sock.
// Pour le composant, chaque test fait `await import(...)` lui-même (imports
// dynamiques avec chemin variable cassent le bundler).

import { vi } from "vitest";
import { FakeWebSocket } from "./setup";

export async function setupWs(): Promise<{
  ws: typeof import("../ws").ws;
  sock: FakeWebSocket;
}> {
  vi.resetModules();
  FakeWebSocket.instances = [];
  const { ws } = await import("../ws");
  ws.connect();
  const sock = FakeWebSocket.instances[0];
  sock._triggerOpen();
  return { ws, sock };
}
