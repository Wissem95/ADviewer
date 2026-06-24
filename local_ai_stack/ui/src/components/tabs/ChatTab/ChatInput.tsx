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

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    // Bloque l'envoi pendant composition IME (japonais/coréen/chinois) :
    // `Enter` valide la composition plutôt qu'envoyer le message.
    if ((e.nativeEvent as KeyboardEvent).isComposing) return;
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <div className="border-t border-border px-4 py-3 bg-panel">
      <div className="flex gap-2 mb-2.5 items-center">
        {MENTIONS.map((m) => (
          <button
            key={m.key}
            onClick={() => setActiveMention(activeMention === m.key ? null : m.key)}
            aria-pressed={activeMention === m.key}
            className={[
              "text-[13px] px-2.5 py-1 rounded-md border transition-colors",
              activeMention === m.key
                ? "bg-accent/15 border-accent text-accent"
                : "border-border text-muted hover:text-text hover:border-border-bright",
            ].join(" ")}
          >
            {m.label}
          </button>
        ))}
        <span className="ml-auto text-[13px] text-muted" data-testid="routing-label">
          {activeMention ? `→ ${activeMention}` : "Auto-routing"}
        </span>
      </div>

      <div className="flex gap-2 items-end rounded-xl border border-border bg-bg px-3 py-2.5 focus-within:border-accent transition-colors">
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Décris ta tâche…  (Enter pour envoyer · Shift+Enter pour une nouvelle ligne)"
          aria-label="Chat prompt"
          disabled={disabled}
          rows={3}
          style={{ caretColor: "var(--accent)" }}
          className="flex-1 bg-transparent text-text px-1 outline-none
                     placeholder:text-muted resize-none disabled:opacity-50"
        />
        <button
          onClick={handleSend}
          disabled={!value.trim() || disabled}
          aria-label="Send"
          style={{ background: "linear-gradient(125deg,#34d8e6,#7b6cff 55%,#ff5fa2)" }}
          className="shrink-0 grid place-items-center w-9 h-9 rounded-lg text-bg font-bold accent-glow-hover
                     disabled:opacity-30 disabled:cursor-not-allowed transition-shadow"
        >
          ↑
        </button>
      </div>
    </div>
  );
}
