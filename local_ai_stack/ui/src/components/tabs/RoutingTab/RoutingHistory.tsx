// Stub — sera complété en Task 9 (tableau historique routing).
import { useRoutingStore } from "../../../stores/routingStore";

export function RoutingHistory() {
  const history = useRoutingStore((s) => s.history);
  return (
    <div className="border border-border rounded p-3 bg-panel">
      <div className="text-muted text-xs mb-1">
        Historique routing ({history.length}) — Task 9
      </div>
    </div>
  );
}
