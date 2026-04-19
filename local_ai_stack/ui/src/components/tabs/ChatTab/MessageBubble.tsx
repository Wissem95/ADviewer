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

const LLM_COLORS: Record<string, string> = {
  "minimax/minimax-m2.5": "bg-accent text-bg",
  "deepseek/deepseek-r1": "bg-[#cba6f7] text-bg",
  "gemini/gemini-2.5-pro": "bg-success text-bg",
  "gemini/gemini-2.5-flash": "bg-[#94e2d5] text-bg",
  "mistral/codestral-2": "bg-warning text-bg",
};

const LLM_ICONS: Record<string, string> = {
  "minimax/minimax-m2.5": "💻",
  "deepseek/deepseek-r1": "💡",
  "gemini/gemini-2.5-pro": "🔍",
  "gemini/gemini-2.5-flash": "⚡",
  "mistral/codestral-2": "🧪",
};

const FALLBACK_COLOR = "bg-muted text-white";
const FALLBACK_ICON = "🤖";

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

  const colorClass = (message.llm && LLM_COLORS[message.llm]) ?? FALLBACK_COLOR;
  const icon = (message.llm && LLM_ICONS[message.llm]) ?? FALLBACK_ICON;

  return (
    <div className="flex flex-col gap-1 mb-4" data-testid={`msg-${message.id}`}>
      {message.llmName && (
        <div className="flex items-center gap-2">
          <span
            className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${colorClass}`}
            data-testid={`badge-${message.id}`}
          >
            {icon} {message.llmName}
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
