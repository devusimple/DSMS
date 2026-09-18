import { useCallback, useEffect, useState } from 'react'
import { Database, Plus } from 'lucide-react'

import { api } from '@/lib/api'
import type { Connection } from '@/lib/types'
import { toast } from '@/components/toaster'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { CreateConnectionDialog } from '@/components/CreateConnectionDialog'
import { SchemaView } from '@/components/SchemaView'

function ConnectionsPanel({
  connections,
  activeId,
  onSelect,
  onCreate,
}: {
  connections: Connection[]
  activeId: string | null
  onSelect: (id: string) => void
  onCreate: (conn: Connection) => void
}) {
  const [dialogOpen, setDialogOpen] = useState(false)

  const handleDelete = async (conn: Connection) => {
    if (!window.confirm(`Delete connection "${conn.name}"?`)) return
    try {
      await api.deleteConnection(conn.id)
      toast(`Removed "${conn.name}"`, 'success')
      if (activeId === conn.id) onSelect('')
    } catch (err) {
      toast((err as Error).message, 'error')
    }
  }

  return (
    <aside className="flex w-64 shrink-0 flex-col border-r bg-muted/30">
      <div className="flex items-center gap-2 border-b p-4">
        <Database className="size-5" />
        <h1 className="text-sm font-semibold">DSMS</h1>
      </div>
      <div className="flex items-center justify-between px-4 py-2">
        <span className="text-xs font-medium text-muted-foreground">Connections</span>
        <Button variant="ghost" size="icon" onClick={() => setDialogOpen(true)} title="New connection">
          <Plus className="size-4" />
        </Button>
      </div>
      <nav className="flex-1 space-y-1 overflow-y-auto p-2">
        {connections.map((conn) => (
          <div
            key={conn.id}
            className={cn(
              'group flex cursor-pointer items-center justify-between rounded-md px-3 py-2 text-sm',
              conn.id === activeId
                ? 'bg-primary text-primary-foreground'
                : 'hover:bg-accent'
            )}
            onClick={() => onSelect(conn.id)}
          >
            <span className="truncate">
              {conn.name}
              <span className={cn('ml-1 text-xs', conn.id === activeId ? 'opacity-80' : 'text-muted-foreground')}>
                ({conn.dialect})
              </span>
            </span>
            <button
              className={cn(
                'rounded-sm px-1 opacity-0 group-hover:opacity-100',
                conn.id === activeId ? 'hover:bg-primary-foreground/20' : 'hover:bg-accent'
              )}
              title="Remove"
              onClick={(e) => {
                e.stopPropagation()
                handleDelete(conn)
              }}
            >
              ×
            </button>
          </div>
        ))}
      </nav>
      <CreateConnectionDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        onCreate={(conn) => {
          onCreate(conn)
          setDialogOpen(false)
        }}
      />
    </aside>
  )
}

export default function App() {
  const [connections, setConnections] = useState<Connection[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)

  const load = useCallback(() => {
    api
      .listConnections()
      .then(setConnections)
      .catch((err) => toast((err as Error).message, 'error'))
  }, [])

  useEffect(load, [load])

  const active = connections.find((c) => c.id === activeId) ?? null

  return (
    <div className="flex h-screen overflow-hidden">
      <ConnectionsPanel
        connections={connections}
        activeId={activeId}
        onSelect={(id) => setActiveId(id)}
        onCreate={(conn) => setConnections((prev) => [...prev, conn])}
      />
      <main className="min-w-0 flex-1 overflow-auto">
        {active ? (
          <SchemaView key={active.id} connection={active} />
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
            <Database className="size-12 opacity-40" />
            <p className="text-sm">Select a connection to browse its schema.</p>
            <p className="text-xs">Or click + to add a new database connection.</p>
          </div>
        )}
      </main>
    </div>
  )
}