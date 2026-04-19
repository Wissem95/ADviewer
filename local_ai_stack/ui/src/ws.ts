// Singleton WebSocket — une seule connexion partagée.
// Reconnexion auto 2s. Handlers par type de message.
// C16 : buffer pendingMessages envoyés avant OPEN.
// I7 : émet l'event local "health" dans onopen (pas besoin que le backend l'envoie).

type WSHandler = (data: unknown) => void;

interface PendingMessage {
  type: string;
  data: unknown;
}

class WSClient {
  private socket: WebSocket | null = null;
  private handlers: Map<string, WSHandler[]> = new Map();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private pendingMessages: PendingMessage[] = [];
  readonly url = "ws://127.0.0.1:8765/ws";

  connect(): void {
    if (this.socket?.readyState === WebSocket.OPEN) return;

    this.socket = new WebSocket(this.url);

    this.socket.onopen = () => {
      console.log("[WS] Connected to backend");
      if (this.reconnectTimer) {
        clearTimeout(this.reconnectTimer);
        this.reconnectTimer = null;
      }
      // I7 — émettre l'event health local aux handlers
      this.dispatch("health", {});
      // C16 — flush la queue
      while (this.pendingMessages.length > 0) {
        const msg = this.pendingMessages.shift()!;
        this.socket!.send(JSON.stringify(msg));
      }
    };

    this.socket.onmessage = (event: MessageEvent) => {
      try {
        const msg = JSON.parse(event.data as string) as { type: string; data: unknown };
        this.dispatch(msg.type, msg.data);
      } catch {
        // Message non-JSON ignoré silencieusement
      }
    };

    this.socket.onclose = () => {
      console.log("[WS] Disconnected — retrying in 2s");
      // Notifier les listeners avant de planifier la reconnexion.
      this.dispatch("disconnect", {});
      this.reconnectTimer = setTimeout(() => this.connect(), 2000);
    };

    this.socket.onerror = (err) => {
      console.error("[WS] Error:", err);
    };
  }

  on(type: string, handler: WSHandler): () => void {
    if (!this.handlers.has(type)) {
      this.handlers.set(type, []);
    }
    this.handlers.get(type)!.push(handler);
    return () => {
      const list = this.handlers.get(type) ?? [];
      const idx = list.indexOf(handler);
      if (idx !== -1) list.splice(idx, 1);
    };
  }

  send(type: string, data: unknown): void {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify({ type, data }));
    } else {
      // C16 — buffer en attente de OPEN
      this.pendingMessages.push({ type, data });
    }
  }

  disconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.socket?.close();
  }

  private dispatch(type: string, data: unknown): void {
    const list = this.handlers.get(type) ?? [];
    list.forEach((h) => h(data));
  }
}

// Singleton exporté
export const ws = new WSClient();
