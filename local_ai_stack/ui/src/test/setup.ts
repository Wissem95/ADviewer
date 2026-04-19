import "@testing-library/jest-dom/vitest";

// Mock WebSocket global — partagé entre tests.
// Permet aux tests d'appeler _triggerOpen()/_triggerMessage() via
// FakeWebSocket.instances[i].
export class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  static OPEN = 1;
  static CLOSED = 3;

  url: string;
  readyState = 0;
  sent: string[] = [];

  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onmessage: ((ev: { data: string }) => void) | null = null;
  onerror: ((ev: unknown) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }

  send(data: string) {
    this.sent.push(data);
  }

  close() {
    this.readyState = FakeWebSocket.CLOSED;
    this.onclose?.();
  }

  _triggerOpen() {
    this.readyState = FakeWebSocket.OPEN;
    this.onopen?.();
  }

  _triggerMessage(type: string, data: unknown) {
    this.onmessage?.({ data: JSON.stringify({ type, data }) });
  }
}

// @ts-expect-error override global
globalThis.WebSocket = FakeWebSocket;
// @ts-expect-error
globalThis.WebSocket.OPEN = 1;
// @ts-expect-error
globalThis.WebSocket.CLOSED = 3;
