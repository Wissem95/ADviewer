import { useRoutingStore } from "../../../stores/routingStore";
import { ROUTING_MODE_COLOR } from "../../../lib/statusMaps";

export function RoutingHistory() {
  const history = useRoutingStore((s) => s.history);

  return (
    <div className="flex-1 overflow-hidden flex flex-col rounded-lg bg-panel border border-border">
      <div className="px-4 py-2 border-b border-border">
        <h3 className="text-xs font-medium text-muted uppercase tracking-wider">
          Historique ({history.length})
        </h3>
      </div>
      <div className="flex-1 overflow-y-auto">
        {history.length === 0 ? (
          <p className="p-4 text-muted text-sm">Aucune décision enregistrée.</p>
        ) : (
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border">
                <th className="px-3 py-2 text-left text-muted font-medium">Prompt</th>
                <th className="px-3 py-2 text-left text-muted font-medium">LLM</th>
                <th className="px-3 py-2 text-left text-muted font-medium">Mode</th>
                <th className="px-3 py-2 text-left text-muted font-medium">Durée</th>
                <th className="px-3 py-2 text-left text-muted font-medium">Tokens</th>
              </tr>
            </thead>
            <tbody>
              {history.map((entry) => (
                <tr
                  key={entry.id}
                  className="border-b border-border hover:bg-border"
                  data-testid={`history-row-${entry.id}`}
                >
                  <td className="px-3 py-2 text-text max-w-[200px]">
                    <span className="block truncate" title={entry.prompt}>
                      {entry.prompt}
                    </span>
                    <span className="text-[9px] text-muted">{entry.reason}</span>
                  </td>
                  <td className="px-3 py-2 text-accent">{entry.llm.split("/").pop()}</td>
                  <td className="px-3 py-2">
                    <span
                      className={`font-medium ${ROUTING_MODE_COLOR[entry.mode] ?? "text-muted"}`}
                    >
                      {entry.mode}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-muted">
                    {(entry.durationMs / 1000).toFixed(1)}s
                  </td>
                  <td className="px-3 py-2 text-muted">{entry.tokens.toLocaleString("en-US")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
