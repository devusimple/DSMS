import { useCallback, useEffect, useState } from "react";
import { Database } from "lucide-react";

import { api } from "@/lib/api";
import type { Connection } from "@/lib/types";
import { toast } from "@/components/toaster";
import { Sidebar } from "@/components/Sidebar";
import { SchemaView } from "@/components/SchemaView";

export default function App() {
  const [connections, setConnections] = useState<Connection[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);

  const load = useCallback(() => {
    api
      .listConnections()
      .then(setConnections)
      .catch((err) => toast((err as Error).message, "error"));
  }, []);

  useEffect(load, [load]);

  const active = connections.find((c) => c.id === activeId) ?? null;

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar
        connections={connections}
        activeId={activeId}
        onSelect={setActiveId}
        onCreate={(conn) => setConnections((prev) => [...prev, conn])}
      />
      <main className="min-w-0 flex-1 overflow-auto">
        {active ? (
          <SchemaView key={active.id} connection={active} />
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
            <Database className="size-12 opacity-40" />
            <p className="text-sm">Select a connection to browse its schema.</p>
            <p className="text-xs">
              Or click + to add a new database connection.
            </p>
          </div>
        )}
      </main>
    </div>
  );
}
