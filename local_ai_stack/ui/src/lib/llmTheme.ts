// Source unique de vérité : couleur badge + icone par LLM id.
// Utilisé par MessageBubble (et potentiellement StatusBar/MonitoringTab plus tard).

export interface LLMTheme {
  badgeClass: string;
  icon: string;
}

const THEMES: Record<string, LLMTheme> = {
  "minimax/minimax-m2.5": { badgeClass: "bg-accent text-bg", icon: "💻" },
  "deepseek/deepseek-r1": { badgeClass: "bg-[#cba6f7] text-bg", icon: "💡" },
  "gemini/gemini-2.5-pro": { badgeClass: "bg-success text-bg", icon: "🔍" },
  "gemini/gemini-2.5-flash": { badgeClass: "bg-[#94e2d5] text-bg", icon: "⚡" },
  "mistral/codestral-2": { badgeClass: "bg-warning text-bg", icon: "🧪" },
};

const FALLBACK: LLMTheme = { badgeClass: "bg-muted text-white", icon: "🤖" };

export function getLLMTheme(llmId: string | undefined): LLMTheme {
  if (!llmId) return FALLBACK;
  return THEMES[llmId] ?? FALLBACK;
}
