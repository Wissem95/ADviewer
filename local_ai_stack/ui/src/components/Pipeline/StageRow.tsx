// StageRow — une ligne d'étape du pipeline.
// Plan 5A Task 13.
//
// Affiche : index + nom + badge LLM + statut + durée + coût.
// Collapsible : sur clic, déploie l'erreur si failed.
import { useState, type JSX } from "react";
import type { StageProgress, StageStatus } from "../../types/pipeline";

interface Props {
  index: number;
  stage: StageProgress;
}

const STATUS_ICON: Record<StageStatus, string> = {
  pending: "⌛",
  running: "⏳",
  done: "✓",
  failed: "✗",
};

const STATUS_COLOR: Record<StageStatus, string> = {
  pending: "text-zinc-400",
  running: "text-blue-500",
  done: "text-green-600",
  failed: "text-red-600",
};

const formatDuration = (ms: number): string => {
  if (ms === 0) return "—";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
};

const formatUSD = (v: number): string => (v === 0 ? "—" : `$${v.toFixed(4)}`);

export function StageRow({ index, stage }: Props): JSX.Element {
  const [expanded, setExpanded] = useState(false);
  const canExpand = stage.status === "failed" && !!stage.error;

  return (
    <div
      data-testid={`stage-row-${stage.name}`}
      className="border-b border-zinc-200 dark:border-zinc-800 py-2"
    >
      <div className="flex items-center gap-3 text-sm">
        <span className="text-zinc-400 w-6 text-right">{index + 1}.</span>
        <span
          className={`w-5 text-center ${STATUS_COLOR[stage.status]}`}
          aria-label={stage.status}
        >
          {STATUS_ICON[stage.status]}
        </span>
        <span className="font-medium flex-1">{stage.name}</span>
        {stage.llm && (
          <span className="px-2 py-0.5 text-xs rounded bg-zinc-200 dark:bg-zinc-700 text-zinc-700 dark:text-zinc-300">
            {stage.llm}
          </span>
        )}
        <span className="text-zinc-500 w-16 text-right">
          {formatDuration(stage.durationMs)}
        </span>
        <span className="text-zinc-500 w-20 text-right">
          {formatUSD(stage.costUSD)}
        </span>
        {canExpand && (
          <button
            onClick={() => setExpanded((v) => !v)}
            className="text-xs text-blue-600 hover:underline"
            aria-label="Toggle details"
          >
            {expanded ? "Moins" : "Plus"}
          </button>
        )}
      </div>
      {expanded && stage.error && (
        <pre className="mt-2 ml-14 text-xs text-red-700 dark:text-red-400 whitespace-pre-wrap">
          {stage.error}
        </pre>
      )}
    </div>
  );
}
