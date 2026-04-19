import { useRoutingStore } from "../../../stores/routingStore";

export const STEPS = ["PLAN", "VERIFY", "EXECUTE", "CHECK", "CONFIRM"] as const;

const STEP_ICONS: Record<string, string> = {
  PLAN: "📋",
  VERIFY: "🔍",
  EXECUTE: "⚙️",
  CHECK: "✅",
  CONFIRM: "🎉",
};

export function RoutingLive() {
  const live = useRoutingStore((s) => s.live);

  if (!live) {
    return (
      <div className="rounded-lg bg-panel border border-border p-4 text-muted text-sm">
        Aucune tâche en cours.
      </div>
    );
  }

  const activeIdx = STEPS.indexOf(live.step as (typeof STEPS)[number]);

  return (
    <div className="rounded-lg bg-panel border border-border p-4" data-testid="routing-live">
      <div className="flex items-start gap-3 mb-4">
        <span className="text-lg">🔄</span>
        <div className="min-w-0">
          <p className="text-xs text-muted mb-0.5">Prompt en cours</p>
          <p className="text-sm text-text font-medium line-clamp-2">{live.prompt}</p>
        </div>
        <div className="ml-auto text-right shrink-0">
          <p className="text-[10px] text-muted">LLM cible</p>
          <p className="text-xs text-accent font-medium">{live.llm.split("/").pop()}</p>
          {live.attempt > 1 && (
            <p className="text-[9px] text-warning">Tentative {live.attempt}/3</p>
          )}
        </div>
      </div>

      <div className="flex items-center gap-0" data-testid="pipeline">
        {STEPS.map((step, idx) => {
          const isDone = idx < activeIdx;
          const isActive = idx === activeIdx;

          return (
            <div key={step} className="flex items-center flex-1">
              <div className="flex flex-col items-center flex-1">
                <div
                  data-testid={`step-${step}`}
                  data-state={isDone ? "done" : isActive ? "active" : "pending"}
                  className={[
                    "w-8 h-8 rounded-full flex items-center justify-center text-sm transition-all",
                    isDone
                      ? "bg-success text-bg"
                      : isActive
                        ? "bg-accent text-bg animate-pulse"
                        : "bg-border text-muted",
                  ].join(" ")}
                >
                  {isDone ? "✓" : STEP_ICONS[step]}
                </div>
                <p
                  className={`text-[9px] mt-1 ${
                    isActive ? "text-accent font-medium" : "text-muted"
                  }`}
                >
                  {step}
                </p>
              </div>
              {idx < STEPS.length - 1 && (
                <div
                  className={`h-0.5 w-full ${idx < activeIdx ? "bg-success" : "bg-border"}`}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
