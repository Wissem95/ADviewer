// PlanDiffView — affiche le Plan produit par Stage4aPlan.
// Plan 5C Task 4.
//
// Lit pipelineStore.plan. Panel expandable sous TraceViewer.
import { useState, type JSX } from "react";
import { usePipelineStore } from "../../stores/pipelineStore";
import type { PlanOperation, PlanRisk } from "../../types/pipeline";

const OP_ICON: Record<PlanOperation, string> = {
  edit: "✎",
  create: "+",
  patch: "△",
  delete: "✕",
};

const OP_COLOR: Record<PlanOperation, string> = {
  edit: "text-blue-600 dark:text-blue-400",
  create: "text-green-600 dark:text-green-400",
  patch: "text-orange-600 dark:text-orange-400",
  delete: "text-red-600 dark:text-red-400",
};

const RISK_BADGE: Record<PlanRisk, string> = {
  low: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  medium:
    "bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300",
  high: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
};

export function PlanDiffView(): JSX.Element | null {
  const plan = usePipelineStore((s) => s.plan);
  const [expanded, setExpanded] = useState(true);

  if (!plan) return null;

  const riskClass = RISK_BADGE[plan.estimatedRisk] ?? RISK_BADGE.low;

  return (
    <section
      data-testid="plan-diff-view"
      className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-3"
    >
      <header className="flex items-center justify-between">
        <button
          onClick={() => setExpanded((v) => !v)}
          className="flex items-center gap-2 text-sm font-semibold text-zinc-800 dark:text-zinc-200"
          aria-expanded={expanded}
        >
          <span>{expanded ? "▾" : "▸"}</span>
          <span>
            Plan — {plan.changes.length} change
            {plan.changes.length > 1 ? "s" : ""}
          </span>
        </button>
        <span
          className={`text-[10px] px-2 py-0.5 rounded-full ${riskClass}`}
          data-testid="plan-risk-badge"
        >
          risque {plan.estimatedRisk}
        </span>
      </header>

      {expanded && (
        <div className="mt-2 grid gap-2 text-xs">
          {plan.changes.length > 0 && (
            <ul className="space-y-1">
              {plan.changes.map((c, i) => (
                <li
                  key={i}
                  className="flex items-start gap-2"
                  data-testid={`plan-change-${i}`}
                >
                  <span
                    className={`font-mono shrink-0 ${OP_COLOR[c.operation]}`}
                    aria-label={c.operation}
                  >
                    {OP_ICON[c.operation]}
                  </span>
                  <span className="font-mono text-zinc-700 dark:text-zinc-300 shrink-0">
                    {c.file}
                  </span>
                  <span className="text-zinc-600 dark:text-zinc-400 truncate">
                    — {c.description}
                  </span>
                </li>
              ))}
            </ul>
          )}

          {plan.testsToRun.length > 0 && (
            <div>
              <h4 className="font-medium text-zinc-700 dark:text-zinc-300 mb-1">
                Tests à lancer
              </h4>
              <ul className="list-disc pl-5 text-zinc-600 dark:text-zinc-400 font-mono text-[11px] space-y-0.5">
                {plan.testsToRun.map((t, i) => (
                  <li key={i}>{t}</li>
                ))}
              </ul>
            </div>
          )}

          {plan.rationale && (
            <p
              className="text-zinc-500 dark:text-zinc-500 italic text-[11px]"
              data-testid="plan-rationale"
            >
              {plan.rationale}
            </p>
          )}
        </div>
      )}
    </section>
  );
}
