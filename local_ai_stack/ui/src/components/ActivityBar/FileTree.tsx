import { useEffect, useState } from "react";
import { ws } from "../../ws";

export interface FileNode {
  name: string;
  path: string;
  type: "file" | "dir";
  modified: boolean;
  children?: FileNode[];
}

export function FileTree() {
  const [tree, setTree] = useState<FileNode[]>([]);

  useEffect(() => {
    const cleanups = [
      ws.on("file_tree", (data) => setTree(data as FileNode[])),
      // #3 — re-request au (re)connect.
      ws.on("health", () => ws.send("request_file_tree", {})),
    ];
    ws.send("request_file_tree", {});
    return () => cleanups.forEach((c) => c());
  }, []);

  function renderNode(node: FileNode, depth: number): React.ReactNode {
    return (
      <div key={node.path}>
        <div
          className={[
            "flex items-center gap-1 px-2 py-0.5 cursor-pointer hover:bg-border rounded text-xs",
            node.modified ? "text-warning" : "text-text",
          ].join(" ")}
          style={{ paddingLeft: `${8 + depth * 12}px` }}
          data-testid={`file-${node.path}`}
        >
          <span>{node.type === "dir" ? "📂" : "📄"}</span>
          <span>{node.name}</span>
          {node.modified && <span className="ml-auto text-warning text-[9px]">M</span>}
        </div>
        {node.children?.map((child) => renderNode(child, depth + 1))}
      </div>
    );
  }

  if (tree.length === 0) {
    return (
      <div className="p-3 text-muted text-xs">
        <p className="font-medium mb-1">Fichiers</p>
        <p className="opacity-60">Aucun fichier chargé</p>
      </div>
    );
  }

  return (
    <div className="py-2">
      <p className="px-3 py-1 text-muted text-[10px] uppercase tracking-wider font-medium">
        Fichiers
      </p>
      {tree.map((node) => renderNode(node, 0))}
    </div>
  );
}
