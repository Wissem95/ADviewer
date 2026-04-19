import { useEffect, useRef, useState } from "react";
import { ws } from "../../../ws";
import { MessageBubble, type Message } from "./MessageBubble";
import { ChatInput } from "./ChatInput";

interface ChatResponse {
  content: string;
  llm: string;
  llmName: string;
  tokens?: number;
  durationMs?: number;
}

function newId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `m-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export default function ChatTab() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const cleanup = ws.on("chat_response", (data) => {
      const resp = data as ChatResponse;
      setMessages((prev) => [
        ...prev,
        {
          id: newId(),
          role: "assistant",
          content: resp.content,
          llm: resp.llm,
          llmName: resp.llmName,
          tokens: resp.tokens,
          durationMs: resp.durationMs,
          timestamp: Date.now(),
        },
      ]);
      setIsLoading(false);
    });
    return cleanup;
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView?.({ behavior: "smooth" });
  }, [messages, isLoading]);

  function handleSend(prompt: string, mention: string | null) {
    setMessages((prev) => [
      ...prev,
      { id: newId(), role: "user", content: prompt, timestamp: Date.now() },
    ]);
    setIsLoading(true);
    ws.send("chat", { prompt, mention });
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-4" data-testid="chat-messages">
        {messages.length === 0 && !isLoading && (
          <div className="flex items-center justify-center h-full text-muted text-sm">
            <div className="text-center">
              <p className="text-2xl mb-2">🤖</p>
              <p>Décris une tâche ou un projet.</p>
              <p className="text-xs mt-1 opacity-60">
                Le système choisit le bon LLM automatiquement.
              </p>
            </div>
          </div>
        )}
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        {isLoading && (
          <div className="flex items-center gap-2 text-muted text-sm mb-4" data-testid="loading">
            <div className="flex gap-1">
              <span className="animate-bounce" style={{ animationDelay: "0ms" }}>●</span>
              <span className="animate-bounce" style={{ animationDelay: "150ms" }}>●</span>
              <span className="animate-bounce" style={{ animationDelay: "300ms" }}>●</span>
            </div>
            <span>En cours de traitement...</span>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <ChatInput onSend={handleSend} disabled={isLoading} />
    </div>
  );
}
