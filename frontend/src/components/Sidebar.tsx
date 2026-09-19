import { useEffect, useState } from 'react'
import {
  Database,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Sun,
  Trash2,
} from 'lucide-react'

import { api } from '@/lib/api'
import type { Connection } from '@/lib/types'
import { toast } from '@/components/toaster'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { CreateConnectionDialog } from '@/components/CreateConnectionDialog'

const DIALECT_COLORS: Record<Connection['dialect'], string> = {
  sqlite: 'bg-emerald-500',
  postgresql: 'bg-sky-600',
  mysql: 'bg-amber-500',
}

function avatarFor(conn: Connection) {
  return conn.name.trim().charAt(0).toUpperCase() || '?'
}

export function Sidebar({
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
  const [collapsed, setCollapsed] = useState(false)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [dark, setDark] = useState(() => {
    if (typeof document === 'undefined') return false
    const stored = localStorage.getItem('dsms:theme')
    if (stored) return stored === 'dark'
    return document.documentElement.classList.contains('dark')
  })

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    localStorage.setItem('dsms:theme', dark ? 'dark' : 'light')
  }, [dark])

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

  const handleSelect = (id: string) => {
    onSelect(id)
    setCollapsed(false)
  }

  const toggle = (
    <Button
      variant="ghost"
      size="icon"
      className={cn('size-8', collapsed && 'mx-auto')}
      onClick={() => setCollapsed((c) => !c)}
      title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
    >
      {collapsed ? (
        <PanelLeftOpen className="size-4" />
      ) : (
        <PanelLeftClose className="size-4" />
      )}
    </Button>
  )

  const themeButton = (
    <Button
      variant="ghost"
      size="icon"
      className={cn('size-8 shrink-0', collapsed && 'mx-auto')}
      onClick={() => setDark((d) => !d)}
      title={dark ? 'Switch to light mode' : 'Switch to dark mode'}
    >
      {dark ? <Sun className="size-4" /> : <Moon className="size-4" />}
    </Button>
  )

  return (
    <aside
      className={cn(
        'flex shrink-0 flex-col border-r bg-muted/30 transition-[width] duration-300 ease-in-out',
        collapsed ? 'w-14' : 'w-72'
      )}
    >
      {/* Header */}
      <div
        className={cn(
          'flex h-14 shrink-0 items-center gap-2 border-b overflow-hidden',
          collapsed ? 'justify-center px-2' : 'justify-between px-3'
        )}
      >
        {!collapsed && (
          <div className="flex min-w-0 items-center gap-2">
            <Database className="size-5 shrink-0" />
            <h1 className="truncate text-sm font-semibold whitespace-nowrap">DSMS</h1>
          </div>
        )}
        {!collapsed && themeButton}
        {toggle}
      </div>

      {/* Section label / new connection */}
      <div
        className={cn(
          'flex h-10 shrink-0 items-center overflow-hidden',
          collapsed ? 'justify-center' : 'justify-between px-3'
        )}
      >
        {!collapsed && (
          <span className="text-xs font-medium text-muted-foreground whitespace-nowrap">
            Connections
          </span>
        )}
        <Button
          variant="ghost"
          size="icon"
          className="size-8 shrink-0"
          onClick={() => setDialogOpen(true)}
          title="New connection"
        >
          <Plus className="size-4" />
        </Button>
      </div>

      {/* Connection list */}
      <nav
        className={cn(
          'flex flex-1 flex-col gap-1 overflow-x-hidden overflow-y-auto',
          collapsed ? 'items-center p-2' : 'p-2'
        )}
      >
        {connections.map((conn) => {
          const active = conn.id === activeId
          return collapsed ? (
            <button
              key={conn.id}
              className={cn(
                'flex size-9 shrink-0 items-center justify-center rounded-md transition-colors',
                active ? 'bg-primary text-primary-foreground' : 'hover:bg-accent',
                !active && `text-white ${DIALECT_COLORS[conn.dialect]} opacity-80`
              )}
              title={`${conn.name} (${conn.dialect})`}
              onClick={() => handleSelect(conn.id)}
            >
              <span className="text-xs font-semibold">{avatarFor(conn)}</span>
            </button>
          ) : (
            <div
              key={conn.id}
              className={cn(
                'group flex cursor-pointer items-center justify-between rounded-md px-3 py-2 text-sm',
                active ? 'bg-primary text-primary-foreground' : 'hover:bg-accent'
              )}
              onClick={() => onSelect(conn.id)}
            >
              <span className="flex min-w-0 items-center gap-2">
                <span
                  className={cn(
                    'flex size-5 shrink-0 items-center justify-center rounded-full text-[10px] font-semibold text-white',
                    DIALECT_COLORS[conn.dialect]
                  )}
                >
                  {avatarFor(conn)}
                </span>
                <span className="truncate">
                  {conn.name}
                  <span
                    className={cn(
                      'ml-1 text-xs',
                      active ? 'opacity-80' : 'text-muted-foreground'
                    )}
                  >
                    ({conn.dialect})
                  </span>
                </span>
              </span>
              <button
                className={cn(
                  'rounded-sm p-1 opacity-0 transition-opacity group-hover:opacity-100',
                  active ? 'hover:bg-primary-foreground/20' : 'hover:bg-accent'
                )}
                title="Remove"
                onClick={(e) => {
                  e.stopPropagation()
                  handleDelete(conn)
                }}
              >
                <Trash2 className="size-3.5" />
              </button>
            </div>
          )
        })}
        {connections.length === 0 && !collapsed && (
          <p className="px-3 py-2 text-xs text-muted-foreground">
            No connections yet. Click + to add one.
          </p>
        )}
      </nav>

      {collapsed && (
        <div className="flex shrink-0 justify-center border-t p-2">
          {themeButton}
        </div>
      )}

      <CreateConnectionDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        onCreate={(conn) => {
          onCreate(conn)
          setDialogOpen(false)
          setCollapsed(false)
        }}
      />
    </aside>
  )
}