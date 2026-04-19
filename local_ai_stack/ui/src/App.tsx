import { lazy, Suspense, useState } from "react";
import { ActivityBar } from "./components/ActivityBar/ActivityBar";
import { StatusBar } from "./components/StatusBar/StatusBar";

const ChatTab = lazy(() => import("./components/tabs/ChatTab/ChatTab"));
const TerminalsTab = lazy(() => import("./components/tabs/TerminalsTab/TerminalsTab"));
const RoutingTab = lazy(() => import("./components/tabs/RoutingTab/RoutingTab"));
const MonitoringTab = lazy(() => import("./components/tabs/MonitoringTab/MonitoringTab"));

export type Tab = "chat" | "terminals" | "routing" | "monitoring";

const TAB_LABELS: Record<Tab, string> = {
  chat: "Chat",
  terminals: "Terminaux",
  routing: "Routing Flow",
  monitoring: "Monitoring",
};

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>("chat");

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-bg">
      <div className="flex flex-1 overflow-hidden">
        <ActivityBar />
        <div className="flex flex-col flex-1 overflow-hidden">
          <div className="flex border-b border-border bg-panel shrink-0" role="tablist">
            {(Object.keys(TAB_LABELS) as Tab[]).map((tab) => {
              const selected = activeTab === tab;
              return (
                <button
                  key={tab}
                  role="tab"
                  aria-selected={selected}
                  onClick={() => setActiveTab(tab)}
                  className={[
                    "px-4 py-2 text-sm font-medium transition-colors",
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
          <div className="flex-1 overflow-hidden">
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
