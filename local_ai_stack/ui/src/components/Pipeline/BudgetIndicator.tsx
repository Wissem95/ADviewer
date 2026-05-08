// BudgetIndicator — jauge $ accumulé / cap.
// Plan 5B Task 7.
//
// Affiche "$0.0050 / $1.00 (1%)" + barre de progression.
// Passe au rouge à >= 80%, orange à >= 50%, sinon vert.
import type { JSX } from "react";

interface Props {
  current: number;
  cap: number;
}

export function BudgetIndicator({ current, cap }: Props): JSX.Element {
  const ratio = cap > 0 ? Math.min(current / cap, 1) : 0;
  const percent = Math.round(ratio * 100);

  let barColor = "bg-green-500";
  let textColor = "text-green-700 dark:text-green-400";
  if (ratio >= 0.8) {
    barColor = "bg-red-500";
    textColor = "text-red-700 dark:text-red-400";
  } else if (ratio >= 0.5) {
    barColor = "bg-orange-500";
    textColor = "text-orange-700 dark:text-orange-400";
  }

  return (
    <div
      data-testid="budget-indicator"
      className="flex items-center gap-2 text-xs"
    >
      <span className={`font-mono ${textColor}`}>
        ${current.toFixed(4)} / ${cap.toFixed(2)} ({percent}%)
      </span>
      <div
        className="flex-1 h-1 rounded bg-zinc-200 dark:bg-zinc-700 overflow-hidden"
        role="progressbar"
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className={`h-full transition-all ${barColor}`}
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}
