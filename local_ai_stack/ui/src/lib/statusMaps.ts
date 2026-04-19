// Sources uniques de vérité pour les mappings status → couleur/icone.
// Utilisées par StatusBar, LLMStatus, SprintBoard, GitPanel, MonitoringTab.

import type { LLMStatus } from "../stores/llmStore";
import type { RoadmapTask } from "../stores/roadmapStore";
import type { BackendStatus } from "../stores/sessionStore";

// ── LLM ──────────────────────────────────────────────────────────────────────

export const LLM_STATUS_DOT: Record<LLMStatus, string> = {
  idle: "bg-success",
  busy: "bg-warning animate-pulse",
  disabled: "bg-muted",
  error: "bg-error",
};

export const LLM_STATUS_LABEL: Record<LLMStatus, string> = {
  idle: "Disponible",
  busy: "En cours...",
  disabled: "Désactivé",
  error: "Erreur",
};

// ── Backend (StatusBar) ──────────────────────────────────────────────────────

export const BACKEND_LABEL: Record<BackendStatus, string> = {
  ready: "Backend prêt",
  connecting: "Connexion...",
  error: "Backend erreur",
};

export const BACKEND_COLOR: Record<BackendStatus, string> = {
  ready: "bg-success",
  connecting: "bg-warning",
  error: "bg-error",
};

// ── Roadmap Task (SprintBoard) ───────────────────────────────────────────────

export const TASK_STATUS_COLOR: Record<RoadmapTask["status"], string> = {
  pending: "text-muted",
  in_progress: "text-warning",
  done: "text-success",
  failed: "text-error",
  blocked: "text-accent",
};

export const TASK_STATUS_ICON: Record<RoadmapTask["status"], string> = {
  pending: "○",
  in_progress: "◐",
  done: "●",
  failed: "✕",
  blocked: "⊘",
};

// ── Git file status (GitPanel) ───────────────────────────────────────────────

export type GitFileStatus = "modified" | "added" | "deleted" | "untracked";

export const GIT_STATUS_COLOR: Record<GitFileStatus, string> = {
  modified: "text-warning",
  added: "text-success",
  deleted: "text-error",
  untracked: "text-muted",
};

// ── CI (MonitoringTab) ───────────────────────────────────────────────────────

export type CIStatus = "pending" | "running" | "success" | "failure";

export const CI_COLOR: Record<CIStatus, string> = {
  pending: "text-muted",
  running: "text-warning animate-pulse",
  success: "text-success",
  failure: "text-error",
};

export const CI_ICON: Record<CIStatus, string> = {
  pending: "⏳",
  running: "🔄",
  success: "✅",
  failure: "❌",
};

// ── Routing mode (RoutingHistory) ────────────────────────────────────────────

export const ROUTING_MODE_COLOR: Record<string, string> = {
  simple: "text-success",
  medium: "text-warning",
  multi_agent: "text-error",
};
