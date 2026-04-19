import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";
import { ws } from "./ws";
import { connectLLMStore } from "./stores/llmStore";
import { connectRoutingStore } from "./stores/routingStore";
import { connectRoadmapStore } from "./stores/roadmapStore";
import { connectSessionStore } from "./stores/sessionStore";

connectLLMStore();
connectRoutingStore();
connectRoadmapStore();
connectSessionStore();
ws.connect();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
