import { useLLMStore, type LLMStatus as LLMStatusEnum } from "../../stores/llmStore";

const STATUS_LABEL: Record<LLMStatusEnum, string> = {
  idle: "Disponible",
  busy: "En cours...",
  disabled: "Désactivé",
  error: "Erreur",
};

const STATUS_DOT: Record<LLMStatusEnum, string> = {
  idle: "bg-success",
  busy: "bg-warning animate-pulse",
  disabled: "bg-muted",
  error: "bg-error",
};

export function LLMStatus() {
  const llms = useLLMStore((s) => s.llms);
  const setDisabled = useLLMStore((s) => s.setDisabled);

  return (
    <div className="py-2">
      <p className="px-3 py-1 text-muted text-[10px] uppercase tracking-wider font-medium">
        LLMs
      </p>
      {llms.map((llm) => (
        <div
          key={llm.id}
          className="px-3 py-2 border-b border-border"
          data-testid={`llm-card-${llm.id}`}
        >
          <div className="flex items-center gap-2 mb-1">
            <span className={`w-2 h-2 rounded-full shrink-0 ${STATUS_DOT[llm.status]}`} />
            <span className="text-xs font-medium text-text truncate">{llm.name}</span>
          </div>
          <div className="flex items-center justify-between gap-2">
            <span className="text-[10px] text-muted min-w-0">
              {STATUS_LABEL[llm.status]}
              {llm.status === "busy" && llm.currentTask && (
                <span className="ml-1 opacity-70 truncate block max-w-[120px]">
                  {llm.currentTask}
                </span>
              )}
            </span>
            {llm.status === "error" ? (
              <button
                onClick={() => useLLMStore.getState().setStatus(llm.id, "idle")}
                className="text-[9px] px-1.5 py-0.5 rounded bg-error text-bg font-medium shrink-0"
                title="Remettre le LLM en idle"
              >
                Reset
              </button>
            ) : llm.status !== "busy" ? (
              <button
                onClick={() => setDisabled(llm.id, llm.status !== "disabled")}
                className="text-[9px] px-1.5 py-0.5 rounded bg-border text-muted hover:text-text shrink-0"
              >
                {llm.status === "disabled" ? "Activer" : "Désact."}
              </button>
            ) : null}
          </div>
          <div className="mt-1 text-[10px] text-muted">
            {llm.tokensToday.toLocaleString()} tokens · {llm.latencyMs}ms
          </div>
        </div>
      ))}
    </div>
  );
}
