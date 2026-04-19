import { useEffect, useState } from "react";
import { ws } from "../../ws";

export interface GitFile {
  path: string;
  status: "modified" | "added" | "deleted" | "untracked";
}

const STATUS_COLORS: Record<GitFile["status"], string> = {
  modified: "text-warning",
  added: "text-success",
  deleted: "text-error",
  untracked: "text-muted",
};

export function GitPanel() {
  const [files, setFiles] = useState<GitFile[]>([]);
  const [commitMsg, setCommitMsg] = useState("");
  const [staged, setStaged] = useState<Set<string>>(new Set());

  useEffect(() => {
    const cleanups = [
      ws.on("git_diff_files", (data) => setFiles(data as GitFile[])),
      // #3 — re-request au (re)connect pour rafraîchir après coupure WS.
      ws.on("health", () => ws.send("request_git_diff", {})),
    ];
    ws.send("request_git_diff", {});
    return () => cleanups.forEach((c) => c());
  }, []);

  function toggleStage(path: string) {
    setStaged((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  }

  function handleCommit() {
    if (!commitMsg.trim() || staged.size === 0) return;
    ws.send("git_commit", { files: [...staged], message: commitMsg });
    setCommitMsg("");
    setStaged(new Set());
  }

  const canCommit = commitMsg.trim().length > 0 && staged.size > 0;

  return (
    <div className="py-2 flex flex-col h-full">
      <p className="px-3 py-1 text-muted text-[10px] uppercase tracking-wider font-medium">
        Git
      </p>

      <div className="flex-1 overflow-y-auto" data-testid="git-files">
        {files.length === 0 ? (
          <p className="px-3 py-2 text-muted text-xs opacity-60">Aucun changement</p>
        ) : (
          files.map((f) => (
            <label
              key={f.path}
              className="flex items-center gap-2 px-3 py-1 hover:bg-border cursor-pointer"
              data-testid={`git-file-${f.path}`}
            >
              <input
                type="checkbox"
                checked={staged.has(f.path)}
                onChange={() => toggleStage(f.path)}
                className="w-3 h-3"
              />
              <span className={`text-[10px] truncate ${STATUS_COLORS[f.status]}`}>
                {f.path.split("/").pop()}
              </span>
            </label>
          ))
        )}
      </div>

      <div className="px-2 pb-2 border-t border-border pt-2">
        <input
          type="text"
          value={commitMsg}
          onChange={(e) => setCommitMsg(e.target.value)}
          placeholder="Message de commit..."
          aria-label="Commit message"
          className="w-full bg-border text-text text-xs px-2 py-1 rounded outline-none placeholder:text-muted mb-1"
        />
        <button
          onClick={handleCommit}
          disabled={!canCommit}
          className="w-full py-1 rounded bg-accent text-bg text-xs font-medium disabled:opacity-40"
        >
          Commit ({staged.size})
        </button>
      </div>
    </div>
  );
}
