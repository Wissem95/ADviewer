import { useEffect, useRef, useState } from "react";
import { ws } from "../../../ws";
import { MessageBubble, type Message } from "./MessageBubble";
import { ChatInput } from "./ChatInput";
import { Logo } from "../../Logo";

const HERO_MODELS = [
  { name: "MiniMax M2", color: "#34d8e6" },
  { name: "Gemini Pro", color: "#7b6cff" },
  { name: "Gemini Flash", color: "#9aa3b8" },
  { name: "DeepSeek R1", color: "#ff5fa2" },
  { name: "Codestral", color: "#34d399" },
];

interface ChatResponse {
  content: string;
  llm: string;
  llmName: string;
  tokens?: number;
  durationMs?: number;
}

function newId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `m-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

interface PipelineDone {
  success: boolean;
  mode: string;
  filesModified?: string[];
  costUsd?: number;
  error?: string | null;
}

const WORKSPACE_KEY = "localcoder.workspace";
type PipelineMode = "simple" | "medium" | "complex";

export default function ChatTab() {
  const [messages, setMessages] = useState<Message[]>([]);
  // #2 — pendingCount au lieu de boolean : support 2+ prompts concurrents.
  // Chaque send incrémente ; chaque chat_response décrémente. Loader visible
  // tant que > 0. Évite d'éteindre le loader à la 1re réponse si une 2e est pending.
  const [pendingCount, setPendingCount] = useState(0);
  // Plan 5D Task 11.3 : toggle mode Pipeline (multi-LLM/consensus). Off par
  // défaut → chat legacy inchangé. On → envoie usePipeline + mode + workspace.
  const [usePipeline, setUsePipeline] = useState(false);
  const [mode, setMode] = useState<PipelineMode>("simple");
  const [workspace, setWorkspace] = useState(
    () => (typeof localStorage !== "undefined" && localStorage.getItem(WORKSPACE_KEY)) || "",
  );
  const isLoading = pendingCount > 0;
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const cleanupChat = ws.on("chat_response", (data) => {
      const resp = data as ChatResponse;
      setMessages((prev) => [
        ...prev,
        {
          id: newId(),
          role: "assistant",
          content: resp.content,
          llm: resp.llm,
          llmName: resp.llmName,
          tokens: resp.tokens,
          durationMs: resp.durationMs,
          timestamp: Date.now(),
        },
      ]);
      setPendingCount((n) => Math.max(0, n - 1));
    });

    // Event final du pipeline : récap succès/échec + fichiers modifiés.
    const cleanupDone = ws.on("pipeline_done", (data) => {
      const r = data as PipelineDone;
      const summary = r.success
        ? `✅ Pipeline ${r.mode} terminé — ${(r.filesModified ?? []).length} fichier(s) modifié(s)` +
          ((r.filesModified ?? []).length ? ` : ${(r.filesModified ?? []).join(", ")}` : "")
        : `❌ Pipeline ${r.mode} échoué — ${r.error ?? "erreur inconnue"}`;
      setMessages((prev) => [
        ...prev,
        { id: newId(), role: "assistant", content: summary, llmName: "Pipeline", timestamp: Date.now() },
      ]);
      setPendingCount((n) => Math.max(0, n - 1));
    });

    return () => {
      cleanupChat();
      cleanupDone();
    };
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView?.({ behavior: "smooth" });
  }, [messages, isLoading]);

  function handleSend(prompt: string, mention: string | null) {
    // Mode pipeline : le workspace est requis (le pipeline écrit des fichiers).
    if (usePipeline && !workspace.trim()) {
      setMessages((prev) => [
        ...prev,
        {
          id: newId(),
          role: "assistant",
          content: "⚠️ Renseigne le dossier du projet pour lancer le pipeline.",
          llmName: "Pipeline",
          timestamp: Date.now(),
        },
      ]);
      return;
    }
    setMessages((prev) => [
      ...prev,
      { id: newId(), role: "user", content: prompt, timestamp: Date.now() },
    ]);
    setPendingCount((n) => n + 1);
    if (usePipeline) {
      ws.send("chat", {
        prompt,
        mention,
        usePipeline: true,
        mode,
        workspace_root: workspace.trim(),
      });
    } else {
      // Chemin legacy inchangé (payload identique à l'historique).
      ws.send("chat", { prompt, mention });
    }
  }

  function onWorkspaceChange(value: string) {
    setWorkspace(value);
    if (typeof localStorage !== "undefined") localStorage.setItem(WORKSPACE_KEY, value);
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-4" data-testid="chat-messages">
        {messages.length === 0 && !isLoading && (
          <div className="flex items-center justify-center h-full px-6">
            <div className="text-center max-w-lg fade-in">
              <div className="hero-halo inline-flex mb-6">
                <Logo size={72} glow />
              </div>
              <h2 className="font-display text-2xl font-bold mb-2 text-gradient">
                Décris une tâche ou un projet.
              </h2>
              <p className="text-muted mb-7">Le système choisit le bon LLM automatiquement.</p>
              <div className="flex flex-wrap justify-center gap-2">
                {HERO_MODELS.map((m) => (
                  <span
                    key={m.name}
                    className="inline-flex items-center gap-1.5 text-[12.5px] text-muted
                               border border-border rounded-full px-2.5 py-1 bg-panel/60"
                  >
                    <span className="w-1.5 h-1.5 rounded-full" style={{ background: m.color }} />
                    {m.name}
                  </span>
                ))}
              </div>
            </div>
          </div>
        )}
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        {isLoading && (
          <div className="flex items-center gap-2.5 text-muted mb-4" data-testid="loading">
            <span className="flex gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-accent animate-bounce" style={{ animationDelay: "0ms" }} />
              <span className="w-1.5 h-1.5 rounded-full bg-accent animate-bounce" style={{ animationDelay: "150ms" }} />
              <span className="w-1.5 h-1.5 rounded-full bg-accent animate-bounce" style={{ animationDelay: "300ms" }} />
            </span>
            <span>Réflexion en cours…</span>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Plan 5D Task 11.3 : barre mode Pipeline (multi-LLM). */}
      <div className="flex items-center gap-3 px-4 py-2 border-t border-border text-[13px] bg-panel">
        <label className="flex items-center gap-2 cursor-pointer select-none">
          <input
            type="checkbox"
            aria-label="Activer le mode pipeline"
            checked={usePipeline}
            onChange={(e) => setUsePipeline(e.target.checked)}
            className="accent-[var(--accent)] w-4 h-4"
          />
          <span className={usePipeline ? "text-text" : "text-muted"}>Pipeline (multi-LLM)</span>
        </label>
        {usePipeline && (
          <>
            <span className="text-muted">mode</span>
            <select
              aria-label="Mode pipeline"
              value={mode}
              onChange={(e) => setMode(e.target.value as PipelineMode)}
              className="bg-bg border border-border text-text rounded-md px-2 py-1 outline-none focus:border-accent"
            >
              <option value="simple">simple</option>
              <option value="medium">medium</option>
              <option value="complex">complex</option>
            </select>
            <input
              type="text"
              aria-label="Dossier du projet"
              placeholder="~/chemin/du/projet"
              value={workspace}
              onChange={(e) => onWorkspaceChange(e.target.value)}
              className="flex-1 bg-bg border border-border text-text rounded-md px-2.5 py-1 outline-none
                         focus:border-accent placeholder:text-muted"
            />
          </>
        )}
      </div>

      {/* ChatInput non disabled pendant pending : on autorise 2+ prompts concurrents. */}
      <ChatInput onSend={handleSend} />
    </div>
  );
}
