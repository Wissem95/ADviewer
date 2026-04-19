import { useRoadmapStore } from "../../stores/roadmapStore";
import type { RoadmapTask } from "../../stores/roadmapStore";

const STATUS_COLORS: Record<RoadmapTask["status"], string> = {
  pending: "text-muted",
  in_progress: "text-warning",
  done: "text-success",
  failed: "text-error",
  blocked: "text-accent",
};

const STATUS_ICONS: Record<RoadmapTask["status"], string> = {
  pending: "○",
  in_progress: "◐",
  done: "●",
  failed: "✕",
  blocked: "⊘",
};

export function SprintBoard() {
  const roadmap = useRoadmapStore((s) => s.roadmap);

  if (!roadmap) {
    return (
      <div className="p-3 text-muted text-xs">
        <p className="font-medium mb-1">Sprints</p>
        <p className="opacity-60">Aucun projet actif.</p>
        <p className="opacity-40 mt-1">Décris une app dans le chat pour démarrer.</p>
      </div>
    );
  }

  const sprints = Array.from(new Set(roadmap.tasks.map((t) => t.sprint)));

  return (
    <div className="py-2">
      <p className="px-3 py-1 text-muted text-[10px] uppercase tracking-wider font-medium">
        {roadmap.project}
      </p>
      {sprints.map((sprint) => (
        <div key={sprint} className="mb-2" data-testid={`sprint-${sprint}`}>
          <p className="px-3 py-0.5 text-accent text-[10px] font-medium">{sprint}</p>
          {roadmap.tasks
            .filter((t) => t.sprint === sprint)
            .map((task) => (
              <div
                key={task.id}
                className="px-3 py-1 hover:bg-border"
                data-testid={`task-${task.id}`}
              >
                <div className="flex items-start gap-1.5">
                  <span
                    className={`text-[10px] mt-0.5 ${STATUS_COLORS[task.status]}`}
                    aria-label={task.status}
                  >
                    {STATUS_ICONS[task.status]}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-[10px] text-text truncate">{task.title}</p>
                    <p className="text-[9px] text-muted">
                      [{task.id}] · score {task.estimatedComplexity}/10
                    </p>
                  </div>
                </div>
              </div>
            ))}
        </div>
      ))}
    </div>
  );
}
