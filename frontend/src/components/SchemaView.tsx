import { useEffect, useState } from 'react'
import {
  ChevronRight,
  Eye,
  ListCollapse,
  Plus,
  RefreshCw,
  SquareTerminal,
  Table2,
  Trash2,
} from 'lucide-react'

import { api } from '@/lib/api'
import type { Connection, TableInfo } from '@/lib/types'
import { toast } from '@/components/toaster'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { CreateTableDialog } from '@/components/CreateTableDialog'
import { TableDetail } from '@/components/TableDetail'
import { ViewDetail } from '@/components/ViewDetail'
import { SqlConsole } from '@/components/SqlConsole'

export function SchemaView({
  connection,
}: {
  connection: Connection
}) {
  const [tables, setTables] = useState<TableInfo[] | null>(null)
  const [views, setViews] = useState<string[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [selectedView, setSelectedView] = useState<string | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [collapsed, setCollapsed] = useState(false)
  const [consoleOpen, setConsoleOpen] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const [list, vs] = await Promise.all([
        api.listTables(connection.id),
        api.listViews(connection.id),
      ])
      setTables(list)
      setViews(vs)
      setSelected((cur) => (cur && list.some((t) => t.name === cur) ? cur : list[0]?.name ?? null))
      setSelectedView((cur) => (cur && vs.includes(cur) ? cur : null))
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

  const navigateToTable = (name: string) => {
    if (!tables?.some((t) => t.name === name)) {
      load()
    }
    setSelected(name)
    setSelectedView(null)
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
        <div className="flex shrink-0 items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setConsoleOpen((v) => !v)}
            className={cn(consoleOpen && 'bg-accent text-accent-foreground')}
            title="SQL console — Ctrl+Enter to run"
          >
            <SquareTerminal className="size-4" />
            SQL
          </Button>
          <Button variant="outline" size="sm" onClick={load} disabled={loading}>
            <RefreshCw className={cn('size-4', loading && 'animate-spin')} />
            Refresh
          </Button>
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        <aside
          className={cn(
            'flex shrink-0 flex-col overflow-hidden border-r bg-muted/30 transition-[width] duration-300 ease-in-out',
            collapsed ? 'w-12' : 'w-60'
          )}
        >
          <div
            className={cn(
              'flex h-9 shrink-0 items-center overflow-hidden border-b',
              collapsed ? 'justify-center' : 'justify-between px-2'
            )}
          >
            {!collapsed && (
              <span className="text-xs font-medium text-muted-foreground whitespace-nowrap">
                Tables
              </span>
            )}
            <Button
              variant="ghost"
              size="icon"
              className="size-7 shrink-0"
              onClick={() => setDialogOpen(true)}
              title="Create table"
            >
              <Plus className="size-4" />
            </Button>
          </div>
          <div
            className={cn(
              'flex flex-col gap-1 overflow-x-hidden overflow-y-auto',
              collapsed ? 'items-center p-1.5' : 'p-1.5'
            )}
          >
            {!tables ? (
              collapsed ? (
                <RefreshCw className={cn('size-4 animate-spin text-muted-foreground', !loading && 'hidden')} />
              ) : (
                <p className="px-3 py-2 text-sm text-muted-foreground">
                  {loading ? 'Loading…' : 'No tables'}
                </p>
              )
            ) : collapsed ? (
              tables.map((t) => (
                <button
                  key={t.name}
                  className={cn(
                    'flex size-8 shrink-0 items-center justify-center rounded-md text-xs font-semibold transition-colors',
                    !selectedView && t.name === selected ? 'bg-primary text-primary-foreground' : 'hover:bg-accent'
                  )}
                  title={t.name}
                  onClick={() => {
                    setSelected(t.name)
                    setSelectedView(null)
                  }}
                >
                  {t.name.charAt(0).toUpperCase()}
                </button>
              ))
            ) : (
              tables.map((t) => (
                <div
                  key={t.name}
                  className={cn(
                    'group flex cursor-pointer items-center justify-between rounded-md px-3 py-1.5 text-sm',
                    !selectedView && t.name === selected ? 'bg-accent' : 'hover:bg-muted/60'
                  )}
                  onClick={() => {
                    setSelected(t.name)
                    setSelectedView(null)
                  }}
                >
                  <span className="flex min-w-0 items-center gap-1.5 truncate">
                    <Table2 className="size-3.5 shrink-0 text-muted-foreground" />
                    {t.name}
                  </span>
                  <button
                    className="rounded-sm p-1 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 hover:text-destructive"
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

            {views.length > 0 && !collapsed && (
              <div className="mt-2 flex items-center gap-1.5 px-3 text-[11px] font-medium text-muted-foreground">
                <Eye className="size-3" /> Views
              </div>
            )}
            {views.map((v) =>
              collapsed ? (
                <button
                  key={v}
                  className={cn(
                    'flex size-8 shrink-0 items-center justify-center rounded-md text-xs font-semibold transition-colors',
                    !!selectedView && v === selectedView
                      ? 'bg-primary text-primary-foreground'
                      : 'hover:bg-accent'
                  )}
                  title={v}
                  onClick={() => {
                    setSelectedView(v)
                    setSelected(null)
                  }}
                >
                  {v.charAt(0).toUpperCase()}
                </button>
              ) : (
                <div
                  key={v}
                  className={cn(
                    'flex cursor-pointer items-center gap-1.5 rounded-md px-3 py-1.5 text-sm',
                    !!selectedView && v === selectedView ? 'bg-accent' : 'hover:bg-muted/60'
                  )}
                  onClick={() => {
                    setSelectedView(v)
                    setSelected(null)
                  }}
                >
                  <Eye className="size-3.5 shrink-0 text-muted-foreground" />
                  <span className="truncate">{v}</span>
                </div>
              )
            )}
          </div>
          <div className={cn('border-t p-1.5', collapsed && 'flex justify-center')}>
            <Button
              variant="ghost"
              size="sm"
              className={cn('w-full gap-1.5 text-xs text-muted-foreground', collapsed && 'size-8 w-8 p-0')}
              onClick={() => setCollapsed((c) => !c)}
              title={collapsed ? 'Expand table list' : 'Collapse table list'}
            >
              {collapsed ? (
                <ChevronRight className="size-4" />
              ) : (
                <>
                  <ListCollapse className="size-3.5" />
                  Collapse
                </>
              )}
            </Button>
          </div>
        </aside>

        <section className="min-w-0 flex-1 overflow-auto p-4">
          {selectedTable ? (
            <TableDetail
              connection={connection}
              table={selectedTable}
              onChanged={load}
              onNavigate={navigateToTable}
            />
          ) : selectedView ? (
            <ViewDetail
              connectionId={connection.id}
              viewName={selectedView}
            />
          ) : (
            <div className="flex h-full flex-col items-center justify-center text-muted-foreground">
              <Table2 className="size-10 opacity-40" />
              <p className="mt-2 text-sm">No table selected.</p>
            </div>
          )}
        </section>

        {consoleOpen && (
          <div className="flex h-full w-[32rem] shrink-0 flex-col overflow-hidden border-l bg-muted/20 p-3">
            <SqlConsole key={connection.id} connection={connection} />
          </div>
        )}
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