// EstimateModal — modal de validation coût avant lancement du pipeline.
// Plan 5A Task 12.
//
// Affiche : classification + raison + tableau des étapes (LLM/tokens/coût/durée)
// + totaux. Trois boutons : Annuler, Forcer simple, Lancer ($X.XX).
import type { JSX } from "react";
import { usePipelineStore } from "../../stores/pipelineStore";
import type { PipelineMode } from "../../types/pipeline";

const formatUSD = (v: number): string => `$${v.toFixed(4)}`;
const formatSec = (v: number): string => `${v.toFixed(1)}s`;

export function EstimateModal(): JSX.Element | null {
  const estimate = usePipelineStore((s) => s.estimate);
  const isOpen = usePipelineStore((s) => s.isAwaitingConfirmation);
  const confirm = usePipelineStore((s) => s.confirm);
  const cancel = usePipelineStore((s) => s.cancel);

  if (!isOpen || !estimate) return null;

  const onConfirm = (mode?: PipelineMode) => () => confirm(mode);

  return (
    <div
      className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center"
      role="dialog"
      aria-modal="true"
      aria-labelledby="estimate-modal-title"
    >
      <div className="bg-white dark:bg-zinc-900 rounded-lg shadow-xl max-w-2xl w-full mx-4 p-6">
        <header className="mb-4">
          <h2
            id="estimate-modal-title"
            className="text-xl font-semibold text-zinc-900 dark:text-zinc-100"
          >
            Confirmer le pipeline
          </h2>
          <p className="text-sm text-zinc-600 dark:text-zinc-400 mt-1">
            <span className="font-medium uppercase">{estimate.classification}</span>
            {" — "}
            {estimate.reason}
          </p>
        </header>

        <table className="w-full text-sm mb-4">
          <thead>
            <tr className="text-left border-b border-zinc-200 dark:border-zinc-700">
              <th className="py-2">Étape</th>
              <th className="py-2">LLM</th>
              <th className="py-2 text-right">Tokens</th>
              <th className="py-2 text-right">Coût</th>
              <th className="py-2 text-right">Durée</th>
            </tr>
          </thead>
          <tbody>
            {estimate.stages.map((s) => (
              <tr key={s.name} className="border-b border-zinc-100 dark:border-zinc-800">
                <td className="py-2">{s.name}</td>
                <td className="py-2 text-zinc-500">{s.llm}</td>
                <td className="py-2 text-right">
                  {s.tokensIn}/{s.tokensOut}
                </td>
                <td className="py-2 text-right">{formatUSD(s.costUSD)}</td>
                <td className="py-2 text-right">{formatSec(s.durationSec)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="font-semibold">
              <td className="py-2" colSpan={3}>
                Total
              </td>
              <td className="py-2 text-right">{formatUSD(estimate.totalCostUSD)}</td>
              <td className="py-2 text-right">{formatSec(estimate.totalDurationSec)}</td>
            </tr>
          </tfoot>
        </table>

        <div className="flex justify-end gap-2">
          <button
            onClick={cancel}
            className="px-4 py-2 text-sm rounded border border-zinc-300 dark:border-zinc-700 hover:bg-zinc-100 dark:hover:bg-zinc-800"
          >
            Annuler
          </button>
          <button
            onClick={onConfirm("simple")}
            className="px-4 py-2 text-sm rounded border border-zinc-300 dark:border-zinc-700 hover:bg-zinc-100 dark:hover:bg-zinc-800"
          >
            Forcer simple
          </button>
          <button
            onClick={onConfirm()}
            className="px-4 py-2 text-sm rounded bg-blue-600 text-white hover:bg-blue-700"
          >
            Lancer ({formatUSD(estimate.totalCostUSD)})
          </button>
        </div>
      </div>
    </div>
  );
}
