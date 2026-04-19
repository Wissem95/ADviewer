// Stub — sera complété en Task 9 (animation routing en cours).
import { useRoutingStore } from "../../../stores/routingStore";

export function RoutingLive() {
  const live = useRoutingStore((s) => s.live);
  return (
    <div className="border border-border rounded p-3 bg-panel">
      <div className="text-muted text-xs mb-1">Routing en cours (Task 9)</div>
      {live ? (
        <div className="text-sm">
          <span className="text-accent">{live.llm}</span> · {live.step} (tentative {live.attempt})
        </div>
      ) : (
        <div className="text-muted text-xs">Aucune décision en cours</div>
      )}
    </div>
  );
}
