// StreamingBubble — affiche le buffer de tokens en cours de streaming.
// Plan 5B Task 5.
//
// Lit pipelineStore.streamingBuffer / streamingStage / streamingLLM. Affiche
// un curseur clignotant `▎` à la fin du texte. Caché si buffer vide.
import type { JSX } from "react";
import { usePipelineStore } from "../../stores/pipelineStore";
import { getLLMTheme } from "../../lib/llmTheme";

export function StreamingBubble(): JSX.Element | null {
  const buffer = usePipelineStore((s) => s.streamingBuffer);
  const stage = usePipelineStore((s) => s.streamingStage);
  const llm = usePipelineStore((s) => s.streamingLLM);

  if (!buffer) return null;

  const theme = getLLMTheme(llm ?? undefined);

  return (
    <div
      data-testid="streaming-bubble"
      className="flex flex-col gap-1 mb-4"
    >
      <div className="flex items-center gap-2">
        {llm && (
          <span
            className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${theme.badgeClass}`}
          >
            {theme.icon} {llm}
          </span>
        )}
        {stage && (
          <span className="text-[10px] text-muted">streaming · {stage}</span>
        )}
      </div>
      <div className="max-w-[85%] bg-panel border border-border rounded-2xl rounded-tl-sm px-4 py-3">
        <p className="text-sm text-text whitespace-pre-wrap leading-relaxed">
          {buffer}
          <span
            className="inline-block w-[2px] h-4 ml-0.5 bg-current align-middle animate-pulse"
            aria-hidden="true"
          />
        </p>
      </div>
    </div>
  );
}
