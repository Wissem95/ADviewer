import { useEffect, useState } from "react";
import { useLLMStore } from "../../../stores/llmStore";
import { useSessionStore } from "../../../stores/sessionStore";
import { ws } from "../../../ws";
import { CI_COLOR, CI_ICON, type CIStatus as CIStatusEnum } from "../../../lib/statusMaps";

interface SystemStats {
  cpuPercent: number;
  ramMB: number;
}

interface CIStatus {
  ticketId: string;
  status: CIStatusEnum;
  url: string;
}

export default function MonitoringTab() {
  const llms = useLLMStore((s) => s.llms);
  const tokensToday = useSessionStore((s) => s.tokensToday);
  const estimatedCostUSD = useSessionStore((s) => s.estimatedCostUSD);
  const [sysStats, setSysStats] = useState<SystemStats>({ cpuPercent: 0, ramMB: 0 });
  const [ciStatuses, setCIStatuses] = useState<CIStatus[]>([]);

  useEffect(() => {
    const cleanups = [
      ws.on("sys_stats", (data) => {
        // Validation défensive : payload backend peut être partiel/corrompu.
        const d = (data ?? {}) as Partial<SystemStats>;
        setSysStats({
          cpuPercent: typeof d.cpuPercent === "number" && !Number.isNaN(d.cpuPercent) ? d.cpuPercent : 0,
          ramMB: typeof d.ramMB === "number" && !Number.isNaN(d.ramMB) ? d.ramMB : 0,
        });
      }),
      ws.on("ci_status", (data) => {
        const status = data as CIStatus;
        setCIStatuses((prev) => {
          const idx = prev.findIndex((s) => s.ticketId === status.ticketId);
          if (idx === -1) return [...prev, status];
          return prev.map((s, i) => (i === idx ? status : s));
        });
      }),
      // #3 — re-request au (re)connect.
      ws.on("health", () => ws.send("request_sys_stats", {})),
    ];
    ws.send("request_sys_stats", {});
    return () => cleanups.forEach((c) => c());
  }, []);

  return (
    <div
      className="p-4 grid grid-cols-2 gap-4 h-full overflow-y-auto"
      data-testid="monitoring-grid"
    >
      <section
        className="bg-panel rounded-lg border border-border p-4"
        data-testid="section-system"
      >
        <h3 className="text-xs font-medium text-muted uppercase tracking-wider mb-3">
          Système
        </h3>
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-muted">CPU</span>
            <span className="text-text" data-testid="cpu">
              {sysStats.cpuPercent.toFixed(1)}%
            </span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-muted">RAM</span>
            <span className="text-text" data-testid="ram">
              {sysStats.ramMB} MB
            </span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-muted">Tokens aujourd'hui</span>
            <span className="text-text">{tokensToday.toLocaleString("en-US")}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-muted">Coût estimé</span>
            <span className="text-text">${estimatedCostUSD.toFixed(4)}</span>
          </div>
        </div>
      </section>

      <section
        className="bg-panel rounded-lg border border-border p-4"
        data-testid="section-latency"
      >
        <h3 className="text-xs font-medium text-muted uppercase tracking-wider mb-3">
          LLMs · Latence
        </h3>
        <div className="space-y-2">
          {llms.map((llm) => (
            <div key={llm.id} className="flex items-center gap-2">
              <span className="text-[10px] text-text w-24 truncate">{llm.name}</span>
              <div className="flex-1 bg-border rounded-full h-1.5" aria-hidden>
                <div
                  className="bg-accent h-1.5 rounded-full transition-all"
                  style={{ width: `${Math.min((llm.latencyMs / 10000) * 100, 100)}%` }}
                />
              </div>
              <span className="text-[10px] text-muted w-12 text-right">
                {llm.latencyMs > 0 ? `${(llm.latencyMs / 1000).toFixed(1)}s` : "—"}
              </span>
            </div>
          ))}
        </div>
      </section>

      <section
        className="col-span-2 bg-panel rounded-lg border border-border p-4"
        data-testid="section-ci"
      >
        <h3 className="text-xs font-medium text-muted uppercase tracking-wider mb-3">
          CI GitHub · Statut Tickets
        </h3>
        {ciStatuses.length === 0 ? (
          <p className="text-muted text-sm">Aucun CI en cours.</p>
        ) : (
          <div className="grid grid-cols-3 gap-2">
            {ciStatuses.map((ci) => (
              <div
                key={ci.ticketId}
                className="flex items-center gap-2 bg-border rounded px-3 py-2"
                data-testid={`ci-${ci.ticketId}`}
              >
                <span className={`text-xs font-medium ${CI_COLOR[ci.status]}`}>
                  {CI_ICON[ci.status]} {ci.ticketId}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
