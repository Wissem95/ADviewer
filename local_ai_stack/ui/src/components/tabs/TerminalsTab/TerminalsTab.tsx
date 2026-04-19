// TerminalsTab — grille xterm.js, un terminal par LLM actif.
// C15 : import dynamique inline dans useEffect pour éviter pollution module
// et permettre le code-splitting Vite.
import { useEffect, useRef } from "react";
import { useLLMStore } from "../../../stores/llmStore";
import { ws } from "../../../ws";

type XtermTerminal = import("@xterm/xterm").Terminal;

function LLMTerminal({ llmId, llmName }: { llmId: string; llmName: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const termRef = useRef<XtermTerminal | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    let disposed = false;

    (async () => {
      const { Terminal } = await import("@xterm/xterm");
      const { FitAddon } = await import("@xterm/addon-fit");
      if (disposed || !ref.current) return;

      const term = new Terminal({
        theme: { background: "#181825", foreground: "#cdd6f4", cursor: "#89b4fa" },
        fontSize: 12,
        fontFamily: "JetBrains Mono, Fira Code, monospace",
        rows: 20,
      });
      const fitAddon = new FitAddon();
      term.loadAddon(fitAddon);
      term.open(ref.current);
      fitAddon.fit();
      termRef.current = term;
      term.writeln(`\x1b[36m[${llmName}]\x1b[0m Terminal prêt.`);
    })();

    const cleanupHandler = ws.on("agent_log", (data) => {
      const { llm, line } = data as { llm: string; line: string };
      if (llm === llmId && termRef.current) {
        termRef.current.writeln(line);
      }
    });

    return () => {
      disposed = true;
      cleanupHandler();
      termRef.current?.dispose();
      termRef.current = null;
    };
  }, [llmId, llmName]);

  return (
    <div
      className="flex flex-col h-full bg-panel rounded-lg overflow-hidden border border-border"
      data-testid={`terminal-${llmId}`}
    >
      <div className="flex items-center gap-2 px-3 py-1 border-b border-border bg-border">
        <span className="w-2 h-2 rounded-full bg-success" />
        <span className="text-xs text-text font-medium">{llmName}</span>
      </div>
      <div ref={ref} className="flex-1 p-1" />
    </div>
  );
}

export default function TerminalsTab() {
  const allLlms = useLLMStore((s) => s.llms);
  const llms = allLlms.filter((l) => l.status !== "disabled");

  if (llms.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-muted text-sm">
        Aucun LLM actif.
      </div>
    );
  }

  const gridClass = llms.length === 1 ? "grid-cols-1" : "grid-cols-2";

  return (
    <div className={`grid ${gridClass} gap-2 p-3 h-full`} data-testid="terminals-grid">
      {llms.map((llm) => (
        <LLMTerminal key={llm.id} llmId={llm.id} llmName={llm.name} />
      ))}
    </div>
  );
}
