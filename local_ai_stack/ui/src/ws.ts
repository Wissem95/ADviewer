// Singleton WebSocket — une seule connexion partagée.
// Reconnexion auto 2s. Handlers par type de message.
// C16 : buffer pendingMessages envoyés avant OPEN (plafonné).
// I7 : émet l'event local "health" dans onopen.
// Émet aussi "disconnect" sur close et "error" sur erreur réseau.

type WSHandler = (data: unknown) => void;

interface PendingMessage {
  type: string;
  data: unknown;
}

export const MAX_PENDING_MESSAGES = 100;

class WSClient {
  private socket: WebSocket | null = null;
  private handlers: Map<string, WSHandler[]> = new Map();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private pendingMessages: PendingMessage[] = [];
  readonly url = "ws://127.0.0.1:8765/ws";

  connect(): void {
    // Guard : déjà OPEN ou CONNECTING → pas de nouvelle socket.
    // Évite aussi que React.StrictMode en dev crée 2 sockets (mount/unmount/mount).
    const CONNECTING = 0;
    if (this.socket?.readyState === WebSocket.OPEN) return;
    if (this.socket?.readyState === CONNECTING) return;

    this.socket = new WebSocket(this.url);

    this.socket.onopen = () => {
      console.log("[WS] Connected to backend");
      if (this.reconnectTimer) {
        clearTimeout(this.reconnectTimer);
        this.reconnectTimer = null;
      }
      this.dispatch("health", {});
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
      this.dispatch("disconnect", {});
      this.reconnectTimer = setTimeout(() => this.connect(), 2000);
    };

    this.socket.onerror = (err) => {
      console.error("[WS] Error:", err);
      // #4 — payload sérialisable (un Event DOM JSON.stringify à "{}")
      const message =
        (err as unknown as { message?: string })?.message ??
        (err instanceof Event ? `WebSocket ${err.type}` : String(err));
      this.dispatch("error", { message });
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
      return;
    }
    // C16 — buffer borné avec drop-head pour éviter la fuite mémoire
    // si le backend ne démarre jamais.
    if (this.pendingMessages.length >= MAX_PENDING_MESSAGES) {
      const dropped = this.pendingMessages.shift();
      console.warn("[WS] pendingMessages full, dropping oldest:", dropped?.type);
    }
    this.pendingMessages.push({ type, data });
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
