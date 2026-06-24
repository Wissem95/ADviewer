import { lazy, Suspense, useRef, useState } from "react";
import { ActivityBar } from "./components/ActivityBar/ActivityBar";
import { StatusBar } from "./components/StatusBar/StatusBar";
import { Logo } from "./components/Logo";

const ChatTab = lazy(() => import("./components/tabs/ChatTab/ChatTab"));
const TerminalsTab = lazy(() => import("./components/tabs/TerminalsTab/TerminalsTab"));
const RoutingTab = lazy(() => import("./components/tabs/RoutingTab/RoutingTab"));
const MonitoringTab = lazy(() => import("./components/tabs/MonitoringTab/MonitoringTab"));

export type Tab = "chat" | "terminals" | "routing" | "monitoring";

const TAB_ORDER: Tab[] = ["chat", "terminals", "routing", "monitoring"];

const TAB_LABELS: Record<Tab, string> = {
  chat: "Chat",
  terminals: "Terminaux",
  routing: "Routing Flow",
  monitoring: "Monitoring",
};

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>("chat");
  const tabRefs = useRef<Partial<Record<Tab, HTMLButtonElement | null>>>({});

  function onTabKeyDown(e: React.KeyboardEvent<HTMLButtonElement>, current: Tab) {
    const idx = TAB_ORDER.indexOf(current);
    let next: Tab | null = null;
    if (e.key === "ArrowRight") next = TAB_ORDER[(idx + 1) % TAB_ORDER.length];
    else if (e.key === "ArrowLeft")
      next = TAB_ORDER[(idx - 1 + TAB_ORDER.length) % TAB_ORDER.length];
    else if (e.key === "Home") next = TAB_ORDER[0];
    else if (e.key === "End") next = TAB_ORDER[TAB_ORDER.length - 1];
    if (next) {
      e.preventDefault();
      setActiveTab(next);
      tabRefs.current[next]?.focus();
    }
  }

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-bg text-text">
      {/* Barre de titre */}
      <header className="flex items-center gap-3 px-5 h-14 shrink-0 border-b border-border bg-panel">
        <Logo size={30} glow />
        <span className="font-display text-lg font-bold tracking-tight text-gradient">LocalCoder</span>
        <span className="text-muted text-[13px]">multi-LLM coding agent</span>
        <span className="ml-auto flex items-center gap-2 text-[13px] text-muted">
          <span className="w-2 h-2 rounded-full bg-success animate-pulse" />
          5 modèles actifs
        </span>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <ActivityBar />
        <div className="flex flex-col flex-1 overflow-hidden">
          <div
            className="flex gap-1 px-3 border-b border-border bg-panel shrink-0"
            role="tablist"
            aria-label="Vues principales"
          >
            {TAB_ORDER.map((tab) => {
              const selected = activeTab === tab;
              return (
                <button
                  key={tab}
                  ref={(el) => {
                    tabRefs.current[tab] = el;
                  }}
                  role="tab"
                  id={`tab-${tab}`}
                  aria-selected={selected}
                  aria-controls={`tabpanel-${tab}`}
                  tabIndex={selected ? 0 : -1}
                  onClick={() => setActiveTab(tab)}
                  onKeyDown={(e) => onTabKeyDown(e, tab)}
                  className={[
                    "px-3.5 py-2.5 text-sm transition-colors outline-none border-b-2 -mb-px",
                    "focus-visible:ring-2 focus-visible:ring-accent/50 rounded-t",
                    selected
                      ? "text-text border-accent"
                      : "text-muted border-transparent hover:text-text",
                  ].join(" ")}
                >
                  {TAB_LABELS[tab]}
                </button>
              );
            })}
          </div>
          <div
            role="tabpanel"
            id={`tabpanel-${activeTab}`}
            aria-labelledby={`tab-${activeTab}`}
            className="flex-1 overflow-hidden"
          >
            <Suspense fallback={<div className="p-4 text-muted">Chargement...</div>}>
              {activeTab === "chat" && <ChatTab />}
              {activeTab === "terminals" && <TerminalsTab />}
              {activeTab === "routing" && <RoutingTab />}
              {activeTab === "monitoring" && <MonitoringTab />}
            </Suspense>
          </div>
        </div>
      </div>
      <StatusBar />
    </div>
  );
}
