// TraceViewer — lit pipelineStore.stages et affiche le pipeline en cours.
// Plan 5A Task 13.
//
// Header : prompt + mode + progression "X/Y stages".
// Body : liste de StageRow.
// Footer : bouton Stop (cancel).
import { useEffect, type JSX } from "react";
import { usePipelineStore } from "../../stores/pipelineStore";
import { StageRow } from "./StageRow";
import { StreamingBubble } from "./StreamingBubble";
import { BudgetIndicator } from "./BudgetIndicator";

const DEFAULT_BUDGET_CAP_USD = 1.0;

export function TraceViewer(): JSX.Element | null {
  const estimate = usePipelineStore((s) => s.estimate);
  const stages = usePipelineStore((s) => s.stages);
  const totalCostUSD = usePipelineStore((s) => s.totalCostUSD);
  const finalResult = usePipelineStore((s) => s.finalResult);
  const stop = usePipelineStore((s) => s.stop);
  const isAwaiting = usePipelineStore((s) => s.isAwaitingConfirmation);

  // Plan 5B Task 6 : raccourci Cmd+. (macOS) ou Ctrl+. (autres) → stop.
  useEffect(() => {
    if (!estimate || isAwaiting || finalResult) return;
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === ".") {
        e.preventDefault();
        stop("shortcut");
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [estimate, isAwaiting, finalResult, stop]);

  // Tant que l'utilisateur n'a pas confirmé, le modal s'occupe de l'affichage.
  if (!estimate || stages.length === 0 || isAwaiting) return null;

  const doneCount = stages.filter(
    (s) => s.status === "done" || s.status === "failed",
  ).length;
  const inProgress = !finalResult;

  return (
    <section
      data-testid="trace-viewer"
      className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4"
    >
      <header className="flex items-center justify-between mb-3">
        <div>
          <h3 className="font-semibold text-sm text-zinc-800 dark:text-zinc-200">
            Pipeline {estimate.classification}
          </h3>
          <p className="text-xs text-zinc-500 dark:text-zinc-400 truncate max-w-md">
            {estimate.reason}
          </p>
        </div>
        <div className="text-right text-xs text-zinc-500">
          <div>
            {doneCount}/{stages.length} étapes
          </div>
          <div className="font-mono">${totalCostUSD.toFixed(4)}</div>
        </div>
      </header>

      <div className="mb-2">
        <BudgetIndicator current={totalCostUSD} cap={DEFAULT_BUDGET_CAP_USD} />
      </div>

      <div className="divide-y divide-zinc-100 dark:divide-zinc-800">
        {stages.map((stage, idx) => (
          <StageRow key={stage.name} index={idx} stage={stage} />
        ))}
      </div>

      <StreamingBubble />

      {inProgress && (
        <footer className="mt-3 flex justify-end items-center gap-2">
          <span className="text-[10px] text-zinc-400">⌘. pour interrompre</span>
          <button
            onClick={() => stop("button")}
            className="px-3 py-1 text-xs rounded border border-red-300 dark:border-red-700 text-red-600 hover:bg-red-50 dark:hover:bg-red-950"
          >
            Stop
          </button>
        </footer>
      )}

      {finalResult && (
        <footer className="mt-3 text-sm">
          {finalResult.success ? (
            <span className="text-green-600">
              ✓ Pipeline terminé ({finalResult.filesModified.length} fichier
              {finalResult.filesModified.length > 1 ? "s" : ""} modifié
              {finalResult.filesModified.length > 1 ? "s" : ""})
            </span>
          ) : (
            <span className="text-red-600">
              ✗ Échec
              {finalResult.rollbackPerformed ? " — rollback effectué" : ""}
              {finalResult.error ? ` : ${finalResult.error}` : ""}
            </span>
          )}
        </footer>
      )}
    </section>
  );
}
