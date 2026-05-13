// ConsensusRoundsLog — affiche les rounds R1 ↔ Pro (event WS consensus_round).
// Plan 5C Task 9.
//
// Lit pipelineStore.consensusRounds. Caché si liste vide.
import type { JSX } from "react";
import { usePipelineStore } from "../../stores/pipelineStore";

const VERDICT_BADGE: Record<string, string> = {
  approve: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  revise: "bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300",
  reject: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
};

export function ConsensusRoundsLog(): JSX.Element | null {
  const rounds = usePipelineStore((s) => s.consensusRounds);

  if (rounds.length === 0) return null;

  return (
    <section
      data-testid="consensus-rounds-log"
      className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-3 text-xs"
    >
      <h3 className="font-semibold text-sm mb-2">
        Consensus PLAN — {rounds.length} round{rounds.length > 1 ? "s" : ""}
      </h3>
      <ul className="space-y-2">
        {rounds.map((r, i) => (
          <li
            key={i}
            data-testid={`consensus-round-${r.round}`}
            className="flex flex-col gap-1"
          >
            <div className="flex items-center gap-2">
              <span className="font-mono text-zinc-500">R{r.round}</span>
              <span
                className={`px-2 py-0.5 rounded-full text-[10px] ${
                  VERDICT_BADGE[r.verdict] ?? VERDICT_BADGE.approve
                }`}
              >
                {r.verdict}
              </span>
              <span className="text-zinc-500">
                {r.planSummary.changes_count} change
                {r.planSummary.changes_count > 1 ? "s" : ""} ·{" "}
                {r.planSummary.tests_count} test
                {r.planSummary.tests_count > 1 ? "s" : ""} · risque{" "}
                {r.planSummary.estimated_risk}
              </span>
            </div>
            {r.concerns.length > 0 && (
              <ul className="list-disc pl-5 text-zinc-600 dark:text-zinc-400 text-[11px]">
                {r.concerns.slice(0, 3).map((c, j) => (
                  <li key={j}>{c}</li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
