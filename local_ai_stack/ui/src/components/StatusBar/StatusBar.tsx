import { useLLMStore } from "../../stores/llmStore";
import { useSessionStore } from "../../stores/sessionStore";
import { BACKEND_COLOR, BACKEND_LABEL, LLM_STATUS_DOT } from "../../lib/statusMaps";

// Les pastilles LLM de la StatusBar n'ont pas besoin de l'animate-pulse du
// mapping global ; on retire cette classe pour garder la barre sobre.
const PULSE_CLASS = "animate-pulse";

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
      className="flex items-center gap-4 px-4 py-1.5 bg-panel text-muted text-[13px] shrink-0 border-t border-border"
    >
      <div className="flex items-center gap-2.5" aria-label="LLMs">
        {llms.map((llm) => (
          <div
            key={llm.id}
            className="flex items-center gap-1"
            title={`${llm.name} : ${llm.status}`}
          >
            <span
              data-testid={`status-dot-${llm.id}`}
              className={`w-1.5 h-1.5 rounded-full ${LLM_STATUS_DOT[llm.status].replace(PULSE_CLASS, "").trim()}`}
            />
            <span className="text-[10px] text-text">{llm.name.split(" ")[0]}</span>
          </div>
        ))}
      </div>

      <span className="text-border-bright">│</span>

      <span className="text-text">
        ⎇ {branch}
        {modifiedFiles > 0 && (
          <span className="ml-1 text-muted">({modifiedFiles} modifiés)</span>
        )}
      </span>

      <span className="text-border-bright">│</span>

      <span className="text-accent">
        {tokensToday.toLocaleString("en-US")} tokens · ${estimatedCostUSD.toFixed(3)}
      </span>

      <div className="ml-auto flex items-center gap-1.5 text-text" aria-label="Backend status">
        <span
          data-testid="backend-dot"
          className={`w-1.5 h-1.5 rounded-full ${BACKEND_COLOR[backendStatus]}`}
        />
        <span>{BACKEND_LABEL[backendStatus]}</span>
      </div>
    </div>
  );
}
