import { lazy, Suspense, useRef, useState } from "react";
import { ActivityBar } from "./components/ActivityBar/ActivityBar";
import { StatusBar } from "./components/StatusBar/StatusBar";

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
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-bg">
      <div className="flex flex-1 overflow-hidden">
        <ActivityBar />
        <div className="flex flex-col flex-1 overflow-hidden">
          <div
            className="flex border-b border-border bg-panel shrink-0"
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
                    "px-4 py-2 text-sm font-medium transition-colors outline-none",
                    "focus-visible:ring-2 focus-visible:ring-accent",
                    selected
                      ? "text-text border-b-2 border-accent bg-bg"
                      : "text-muted hover:text-text",
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
