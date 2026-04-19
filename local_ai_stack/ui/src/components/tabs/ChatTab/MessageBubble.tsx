import { getLLMTheme } from "../../../lib/llmTheme";

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  llm?: string;
  llmName?: string;
  durationMs?: number;
  tokens?: number;
  timestamp: number;
}

export function MessageBubble({ message }: { message: Message }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end mb-3" data-testid={`msg-${message.id}`}>
        <div className="max-w-[70%] bg-border rounded-2xl rounded-tr-sm px-4 py-2">
          <p className="text-sm text-text whitespace-pre-wrap">{message.content}</p>
        </div>
      </div>
    );
  }

  const theme = getLLMTheme(message.llm);

  return (
    <div className="flex flex-col gap-1 mb-4" data-testid={`msg-${message.id}`}>
      {message.llmName && (
        <div className="flex items-center gap-2">
          <span
            className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${theme.badgeClass}`}
            data-testid={`badge-${message.id}`}
          >
            {theme.icon} {message.llmName}
          </span>
          {typeof message.durationMs === "number" && (
            <span className="text-[10px] text-muted">
              {(message.durationMs / 1000).toFixed(1)}s
              {typeof message.tokens === "number" ? ` · ${message.tokens} tokens` : ""}
            </span>
          )}
        </div>
      )}
      <div className="max-w-[85%] bg-panel border border-border rounded-2xl rounded-tl-sm px-4 py-3">
        <p className="text-sm text-text whitespace-pre-wrap leading-relaxed">
          {message.content}
        </p>
      </div>
    </div>
  );
}
