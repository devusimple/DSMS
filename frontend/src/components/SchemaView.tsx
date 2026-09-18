import { useEffect, useState } from 'react'
import { Plus, RefreshCw, Table2, Trash2 } from 'lucide-react'

import { api } from '@/lib/api'
import type { Connection, TableInfo } from '@/lib/types'
import { toast } from '@/components/toaster'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { CreateTableDialog } from '@/components/CreateTableDialog'
import { TableDetail } from '@/components/TableDetail'

export function SchemaView({
  connection,
}: {
  connection: Connection
}) {
  const [tables, setTables] = useState<TableInfo[] | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [loading, setLoading] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const list = await api.listTables(connection.id)
      setTables(list)
      setSelected((cur) => (cur && list.some((t) => t.name === cur) ? cur : list[0]?.name ?? null))
    } catch (err) {
      toast((err as Error).message, 'error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [connection.id])

  const dropTable = async (name: string) => {
    if (!window.confirm(`Drop table "${name}"? This cannot be undone.`)) return
    try {
      await api.dropTable(connection.id, name)
      toast(`Dropped "${name}"`, 'success')
      setTables((cur) => (cur ? cur.filter((t) => t.name !== name) : cur))
      setSelected((cur) => (cur === name ? null : cur))
    } catch (err) {
      toast((err as Error).message, 'error')
    }
  }

  const handleCreated = () => {
    setDialogOpen(false)
    load()
  }

  const selectedTable = tables?.find((t) => t.name === selected) ?? null

  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center justify-between gap-2 border-b p-4">
        <div className="min-w-0">
          <h1 className="truncate text-lg font-semibold">{connection.name}</h1>
          <p className="truncate text-xs text-muted-foreground">
            {connection.dialect} · {connection.url}
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={load} disabled={loading}>
          <RefreshCw className={cn('size-4', loading && 'animate-spin')} />
          Refresh
        </Button>
      </header>

      <div className="flex min-h-0 flex-1">
        <aside className="w-56 shrink-0 overflow-y-auto border-r">
          <div className="flex items-center justify-between px-3 py-2">
            <span className="text-xs font-medium text-muted-foreground">Tables</span>
            <Button variant="ghost" size="icon" className="size-7" onClick={() => setDialogOpen(true)} title="Create table">
              <Plus className="size-4" />
            </Button>
          </div>
          {!tables ? (
            <p className="px-3 py-2 text-sm text-muted-foreground">{loading ? 'Loading…' : 'No tables'}</p>
          ) : (
            tables.map((t) => (
              <div
                key={t.name}
                className={cn(
                  'group flex cursor-pointer items-center justify-between px-3 py-1.5 text-sm',
                  t.name === selected ? 'bg-accent' : 'hover:bg-muted/60'
                )}
                onClick={() => setSelected(t.name)}
              >
                <span className="flex min-w-0 items-center gap-1.5 truncate">
                  <Table2 className="size-3.5 shrink-0 text-muted-foreground" />
                  {t.name}
                </span>
                <button
                  className="rounded-sm px-1 text-muted-foreground opacity-0 group-hover:opacity-100 hover:text-destructive"
                  onClick={(e) => {
                    e.stopPropagation()
                    dropTable(t.name)
                  }}
                >
                  <Trash2 className="size-3.5" />
                </button>
              </div>
            ))
          )}
        </aside>

        <section className="min-w-0 flex-1 overflow-auto p-4">
          {selectedTable ? (
            <TableDetail
              connection={connection}
              table={selectedTable}
              onChanged={load}
            />
          ) : (
            <div className="flex h-full flex-col items-center justify-center text-muted-foreground">
              <Table2 className="size-10 opacity-40" />
              <p className="mt-2 text-sm">No table selected.</p>
            </div>
          )}
        </section>
      </div>

      <CreateTableDialog
        open={dialogOpen}
        connId={connection.id}
        onClose={() => setDialogOpen(false)}
        onCreated={handleCreated}
      />
    </div>
  )
}