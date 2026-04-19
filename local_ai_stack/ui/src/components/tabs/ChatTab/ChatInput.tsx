import { useState } from "react";

const MENTIONS = [
  { key: "minimax", label: "@minimax" },
  { key: "gemini", label: "@gemini" },
  { key: "deepseek", label: "@deepseek" },
  { key: "codestral", label: "@codestral" },
];

interface ChatInputProps {
  onSend: (prompt: string, mention: string | null) => void;
  disabled?: boolean;
}

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [value, setValue] = useState("");
  const [activeMention, setActiveMention] = useState<string | null>(null);

  function handleSend() {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed, activeMention);
    setValue("");
    setActiveMention(null);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <div className="border-t border-border p-3 bg-panel">
      <div className="flex gap-1 mb-2">
        {MENTIONS.map((m) => (
          <button
            key={m.key}
            onClick={() => setActiveMention(activeMention === m.key ? null : m.key)}
            aria-pressed={activeMention === m.key}
            className={[
              "text-[10px] px-2 py-0.5 rounded-full border transition-colors",
              activeMention === m.key
                ? "bg-accent border-accent text-bg font-medium"
                : "border-border text-muted hover:text-text",
            ].join(" ")}
          >
            {m.label}
          </button>
        ))}
        <span className="ml-auto text-muted text-[10px] self-center" data-testid="routing-label">
          {activeMention ? `→ ${activeMention}` : "Auto-routing"}
        </span>
      </div>

      <div className="flex gap-2">
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Décris ta tâche... (Enter pour envoyer, Shift+Enter pour nouvelle ligne)"
          aria-label="Chat prompt"
          disabled={disabled}
          rows={3}
          className="flex-1 bg-border text-text text-sm px-3 py-2 rounded-lg outline-none
                     placeholder:text-muted resize-none disabled:opacity-50"
        />
        <button
          onClick={handleSend}
          disabled={!value.trim() || disabled}
          aria-label="Send"
          className="px-4 py-2 bg-accent text-bg rounded-lg font-medium text-sm
                     disabled:opacity-40 transition-colors self-end"
        >
          ↵
        </button>
      </div>
    </div>
  );
}
