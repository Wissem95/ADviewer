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
              className={`w-2 h-2 rounded-full ${LLM_STATUS_DOT[llm.status].replace(PULSE_CLASS, "").trim()}`}
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
        {tokensToday.toLocaleString("en-US")} tokens · ${estimatedCostUSD.toFixed(3)}
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
