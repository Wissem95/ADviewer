import { RoutingLive } from "./RoutingLive";
import { RoutingHistory } from "./RoutingHistory";

export default function RoutingTab() {
  return (
    <div className="flex flex-col h-full p-4 gap-4 overflow-auto">
      <RoutingLive />
      <RoutingHistory />
    </div>
  );
}
