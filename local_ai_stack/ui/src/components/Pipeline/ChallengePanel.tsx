// ChallengePanel — affiche le résultat Stage2Challenge.
// Plan 5C Task 2.
//
// Lit pipelineStore.challenge. Panel expandable sous le TraceViewer.
// Si blocking → banner jaune avec boutons Continuer / Annuler.
import { useState, type JSX } from "react";
import { usePipelineStore } from "../../stores/pipelineStore";

const SEVERITY_BADGE: Record<string, string> = {
  minor: "bg-zinc-200 text-zinc-700 dark:bg-zinc-700 dark:text-zinc-300",
  moderate:
    "bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300",
  critical: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
};

export function ChallengePanel(): JSX.Element | null {
  const challenge = usePipelineStore((s) => s.challenge);
  const challengeBlocking = usePipelineStore((s) => s.challengeBlocking);
  const acknowledgeBlocking = usePipelineStore((s) => s.acknowledgeBlocking);
  const stop = usePipelineStore((s) => s.stop);
  const [expanded, setExpanded] = useState(true);

  if (!challenge) return null;

  const severityClass =
    SEVERITY_BADGE[challenge.severity] ?? SEVERITY_BADGE.minor;

  return (
    <section
      data-testid="challenge-panel"
      className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-3"
    >
      <header className="flex items-center justify-between">
        <button
          onClick={() => setExpanded((v) => !v)}
          className="flex items-center gap-2 text-sm font-semibold text-zinc-800 dark:text-zinc-200"
          aria-expanded={expanded}
        >
          <span>{expanded ? "▾" : "▸"}</span>
          <span>Challenge — avocat du diable</span>
        </button>
        <span className={`text-[10px] px-2 py-0.5 rounded-full ${severityClass}`}>
          {challenge.severity}
        </span>
      </header>

      {challengeBlocking && (
        <div
          data-testid="challenge-blocking-banner"
          className="mt-2 p-2 rounded border border-yellow-300 bg-yellow-50 dark:border-yellow-700 dark:bg-yellow-950 text-xs flex items-center justify-between gap-2"
        >
          <span className="text-yellow-800 dark:text-yellow-200">
            ⚠️ Le LLM challenger pense que tu devrais reconsidérer. Continuer
            quand même ?
          </span>
          <div className="flex gap-2 shrink-0">
            <button
              onClick={() => stop("challenge-blocking")}
              className="px-2 py-0.5 rounded border border-red-300 text-red-600 text-[11px] hover:bg-red-50"
            >
              Annuler
            </button>
            <button
              onClick={acknowledgeBlocking}
              className="px-2 py-0.5 rounded bg-yellow-600 text-white text-[11px] hover:bg-yellow-700"
            >
              Continuer
            </button>
          </div>
        </div>
      )}

      {expanded && (
        <div className="mt-2 grid gap-2 text-xs">
          {challenge.risks.length > 0 && (
            <div>
              <h4 className="font-medium text-zinc-700 dark:text-zinc-300 mb-1">
                Risques
              </h4>
              <ul className="list-disc pl-5 text-zinc-600 dark:text-zinc-400 space-y-0.5">
                {challenge.risks.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            </div>
          )}
          {challenge.edgeCases.length > 0 && (
            <div>
              <h4 className="font-medium text-zinc-700 dark:text-zinc-300 mb-1">
                Edge cases
              </h4>
              <ul className="list-disc pl-5 text-zinc-600 dark:text-zinc-400 space-y-0.5">
                {challenge.edgeCases.map((e, i) => (
                  <li key={i}>{e}</li>
                ))}
              </ul>
            </div>
          )}
          {challenge.alternatives.length > 0 && (
            <div>
              <h4 className="font-medium text-zinc-700 dark:text-zinc-300 mb-1">
                Alternatives
              </h4>
              <ul className="list-disc pl-5 text-zinc-600 dark:text-zinc-400 space-y-0.5">
                {challenge.alternatives.map((a, i) => (
                  <li key={i}>{a}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
