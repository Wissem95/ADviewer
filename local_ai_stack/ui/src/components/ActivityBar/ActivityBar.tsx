import { useState } from "react";
import { FileTree } from "./FileTree";
import { LLMStatus } from "./LLMStatus";
import { GitPanel } from "./GitPanel";
import { SprintBoard } from "./SprintBoard";

export type ActivityPanel = "files" | "llms" | "git" | "sprints";

const ICONS: Record<ActivityPanel, string> = {
  files: "📁",
  llms: "🤖",
  git: "⎇",
  sprints: "📋",
};

const PANELS: Record<ActivityPanel, React.ComponentType> = {
  files: FileTree,
  llms: LLMStatus,
  git: GitPanel,
  sprints: SprintBoard,
};

export function ActivityBar() {
  const [activePanel, setActivePanel] = useState<ActivityPanel>("files");
  const ActivePanel = PANELS[activePanel];

  return (
    <aside className="flex shrink-0 border-r border-border" aria-label="Activity bar">
      <nav
        className="flex flex-col items-center py-2 gap-1 w-10 bg-panel"
        aria-label="Activity panels"
      >
        {(Object.keys(ICONS) as ActivityPanel[]).map((panel) => (
          <button
            key={panel}
            onClick={() => setActivePanel(panel)}
            title={panel}
            aria-pressed={activePanel === panel}
            className={[
              "w-8 h-8 flex items-center justify-center rounded text-base transition-colors",
              activePanel === panel
                ? "bg-border text-text"
                : "text-muted hover:text-text",
            ].join(" ")}
          >
            {ICONS[panel]}
          </button>
        ))}
      </nav>
      <div className="w-56 bg-panel overflow-y-auto" data-testid={`panel-${activePanel}`}>
        <ActivePanel />
      </div>
    </aside>
  );
}
