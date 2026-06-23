import { useEffect, useRef, useState } from "react";
import { ws } from "../../../ws";
import { MessageBubble, type Message } from "./MessageBubble";
import { ChatInput } from "./ChatInput";

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
          <div className="flex items-center justify-center h-full text-muted text-sm">
            <div className="text-center">
              <p className="text-2xl mb-2">🤖</p>
              <p>Décris une tâche ou un projet.</p>
              <p className="text-xs mt-1 opacity-60">
                Le système choisit le bon LLM automatiquement.
              </p>
            </div>
          </div>
        )}
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        {isLoading && (
          <div className="flex items-center gap-2 text-muted text-sm mb-4" data-testid="loading">
            <div className="flex gap-1">
              <span className="animate-bounce" style={{ animationDelay: "0ms" }}>●</span>
              <span className="animate-bounce" style={{ animationDelay: "150ms" }}>●</span>
              <span className="animate-bounce" style={{ animationDelay: "300ms" }}>●</span>
            </div>
            <span>En cours de traitement...</span>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Plan 5D Task 11.3 : barre mode Pipeline (multi-LLM). */}
      <div className="flex items-center gap-2 px-4 py-2 border-t border-border text-xs">
        <label className="flex items-center gap-1.5 cursor-pointer select-none">
          <input
            type="checkbox"
            aria-label="Activer le mode pipeline"
            checked={usePipeline}
            onChange={(e) => setUsePipeline(e.target.checked)}
          />
          <span>Pipeline (multi-LLM)</span>
        </label>
        {usePipeline && (
          <>
            <select
              aria-label="Mode pipeline"
              value={mode}
              onChange={(e) => setMode(e.target.value as PipelineMode)}
              className="bg-transparent border border-border rounded px-1 py-0.5"
            >
              <option value="simple">simple</option>
              <option value="medium">medium</option>
              <option value="complex">complex</option>
            </select>
            <input
              type="text"
              aria-label="Dossier du projet"
              placeholder="/chemin/vers/projet"
              value={workspace}
              onChange={(e) => onWorkspaceChange(e.target.value)}
              className="flex-1 bg-transparent border border-border rounded px-2 py-0.5"
            />
          </>
        )}
      </div>

      {/* ChatInput non disabled pendant pending : on autorise 2+ prompts concurrents. */}
      <ChatInput onSend={handleSend} />
    </div>
  );
}
