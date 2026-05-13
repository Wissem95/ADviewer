// DeadlockModal — modal user-decision quand R1 et Pro ne convergent pas.
// Plan 5C Task 7.
//
// Affiché si pipelineStore.deadlock != null. Présente 2 plans côte-à-côte +
// concerns par round. User choisit "Utiliser Plan A" / "Utiliser Plan B" /
// "Annuler pipeline".
import type { JSX } from "react";
import { usePipelineStore } from "../../stores/pipelineStore";
import type {
  PlanResultPayload,
  PlanOperation,
} from "../../types/pipeline";

const OP_ICON: Record<PlanOperation, string> = {
  edit: "✎",
  create: "+",
  patch: "△",
  delete: "✕",
};

function PlanCard({
  label,
  plan,
  concerns,
  onChoose,
}: {
  label: string;
  plan: PlanResultPayload | undefined;
  concerns: string[] | undefined;
  onChoose: () => void;
}): JSX.Element {
  if (!plan) {
    return (
      <div className="flex-1 rounded border border-zinc-200 dark:border-zinc-700 p-3 text-xs text-zinc-500">
        {label} — non produit
      </div>
    );
  }
  return (
    <div
      data-testid={`plan-card-${label}`}
      className="flex-1 rounded border border-zinc-200 dark:border-zinc-700 p-3 flex flex-col gap-2"
    >
      <header className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">{label}</h3>
        <span className="text-[10px] px-2 py-0.5 rounded-full bg-zinc-200 dark:bg-zinc-700">
          risque {plan.estimatedRisk}
        </span>
      </header>
      <ul className="text-xs space-y-1 max-h-40 overflow-y-auto">
        {plan.changes.map((c, i) => (
          <li key={i} className="flex gap-2 font-mono">
            <span>{OP_ICON[c.operation]}</span>
            <span className="text-zinc-700 dark:text-zinc-300">{c.file}</span>
            <span className="text-zinc-500 truncate">— {c.description}</span>
          </li>
        ))}
      </ul>
      {plan.testsToRun.length > 0 && (
        <p className="text-[11px] text-zinc-500 font-mono">
          {plan.testsToRun.length} test{plan.testsToRun.length > 1 ? "s" : ""}
        </p>
      )}
      {concerns && concerns.length > 0 && (
        <div className="text-[11px] text-orange-600 dark:text-orange-400">
          <p className="font-medium">Pro a relevé :</p>
          <ul className="list-disc pl-4">
            {concerns.slice(0, 3).map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </div>
      )}
      <button
        onClick={onChoose}
        className="mt-auto px-3 py-1 text-xs rounded bg-blue-600 text-white hover:bg-blue-700"
      >
        Utiliser ce plan
      </button>
    </div>
  );
}

export function DeadlockModal(): JSX.Element | null {
  const deadlock = usePipelineStore((s) => s.deadlock);
  const resolveDeadlock = usePipelineStore((s) => s.resolveDeadlock);

  if (!deadlock) return null;

  const [plan1, plan2] = deadlock.plans;
  const [concerns1, concerns2] = deadlock.concerns;

  return (
    <div
      className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="deadlock-modal-title"
      data-testid="deadlock-modal"
    >
      <div className="bg-white dark:bg-zinc-900 rounded-lg shadow-xl max-w-4xl w-full p-6">
        <header className="mb-4">
          <h2
            id="deadlock-modal-title"
            className="text-xl font-semibold"
          >
            ⚖️ Consensus impossible — ta décision
          </h2>
          <p className="text-sm text-zinc-600 dark:text-zinc-400 mt-1">
            R1 et Pro n'ont pas pu se mettre d'accord après 2 rounds. Choisis
            quel plan utiliser, ou annule le pipeline.
          </p>
        </header>

        <div className="flex gap-3 mb-4">
          <PlanCard
            label="Plan A"
            plan={plan1}
            concerns={concerns1}
            onChoose={() => resolveDeadlock("plan1")}
          />
          <PlanCard
            label="Plan B"
            plan={plan2}
            concerns={concerns2}
            onChoose={() => resolveDeadlock("plan2")}
          />
        </div>

        <div className="flex justify-end">
          <button
            onClick={() => resolveDeadlock("cancel")}
            className="px-4 py-2 text-sm rounded border border-red-300 text-red-600 hover:bg-red-50 dark:hover:bg-red-950"
          >
            Annuler le pipeline
          </button>
        </div>
      </div>
    </div>
  );
}
