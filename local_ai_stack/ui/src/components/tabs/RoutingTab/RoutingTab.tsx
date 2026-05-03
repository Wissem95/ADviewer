import { RoutingLive } from "./RoutingLive";
import { RoutingHistory } from "./RoutingHistory";
import { TraceViewer } from "../../Pipeline/TraceViewer";

export default function RoutingTab() {
  return (
    <div className="flex flex-col h-full p-4 gap-4 overflow-auto">
      <TraceViewer />
      <RoutingLive />
      <RoutingHistory />
    </div>
  );
}
