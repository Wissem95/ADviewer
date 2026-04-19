import { useLLMStore } from "../../stores/llmStore";
import { useSessionStore, type BackendStatus } from "../../stores/sessionStore";
import type { LLMStatus } from "../../stores/llmStore";

const STATUS_COLOR: Record<LLMStatus, string> = {
  idle: "bg-success",
  busy: "bg-warning",
  disabled: "bg-muted",
  error: "bg-error",
};

const BACKEND_LABEL: Record<BackendStatus, string> = {
  ready: "Backend prêt",
  connecting: "Connexion...",
  error: "Backend erreur",
};

const BACKEND_COLOR: Record<BackendStatus, string> = {
  ready: "bg-success",
  connecting: "bg-warning",
  error: "bg-error",
};

export function StatusBar() {
  const llms = useLLMStore((s) => s.llms);
  const branch = useSessionStore((s) => s.branch);
  const modifiedFiles = useSessionStore((s) => s.modifiedFiles);
  const tokensToday = useSessionStore((s) => s.tokensToday);
  const estimatedCostUSD = useSessionStore((s) => s.estimatedCostUSD);
  const backendStatus = useSessionStore((s) => s.backendStatus);

  return (
    <div
      role="status"
      aria-label="Status bar"
      className="flex items-center gap-4 px-3 py-1 bg-accent text-bg text-xs font-mono shrink-0"
    >
      <div className="flex items-center gap-2" aria-label="LLMs">
        {llms.map((llm) => (
          <div
            key={llm.id}
            className="flex items-center gap-1"
            title={`${llm.name} : ${llm.status}`}
          >
            <span
              data-testid={`status-dot-${llm.id}`}
              className={`w-2 h-2 rounded-full ${STATUS_COLOR[llm.status]}`}
            />
            <span className="text-[10px]">{llm.name.split(" ")[0]}</span>
          </div>
        ))}
      </div>

      <span className="opacity-40">|</span>

      <span>
        ⎇ {branch}
        {modifiedFiles > 0 && (
          <span className="ml-1 opacity-70">({modifiedFiles} modifiés)</span>
        )}
      </span>

      <span className="opacity-40">|</span>

      <span>
        {tokensToday.toLocaleString()} tokens · ${estimatedCostUSD.toFixed(3)}
      </span>

      <div className="ml-auto flex items-center gap-1" aria-label="Backend status">
        <span
          data-testid="backend-dot"
          className={`w-2 h-2 rounded-full ${BACKEND_COLOR[backendStatus]}`}
        />
        <span>{BACKEND_LABEL[backendStatus]}</span>
      </div>
    </div>
  );
}
