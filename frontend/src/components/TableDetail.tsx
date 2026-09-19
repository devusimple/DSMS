import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  Copy,
  Download,
  KeyRound,
  Pencil,
  Plus,
  Search,
  Trash2,
} from 'lucide-react'

import { api } from '@/lib/api'
import type { ColumnDef, Connection, IndexCreate, IndexInfo, TableInfo } from '@/lib/types'
import { toast } from '@/components/toaster'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { PORTABLE_TYPES } from '@/lib/types_constants'
import { RowEditorDialog } from '@/components/RowEditorDialog'
import { RelationshipsPanel } from '@/components/RelationshipsPanel'

export function TableDetail({
  connection,
  table,
  onChanged,
  onNavigate,
}: {
  connection: Connection
  table: TableInfo
  onChanged: () => void
  onNavigate?: (tableName: string) => void
}) {
  const [tab, setTab] = useState('columns')
  const [addColOpen, setAddColOpen] = useState(false)
  const [rowEditor, setRowEditor] = useState<{ open: boolean; mode: 'create' } | { open: boolean; mode: 'edit'; row: Record<string, unknown>; pk: Record<string, unknown> }>({
    open: false,
    mode: 'create',
  })
  const [deleting, setDeleting] = useState<string | null>(null)

  const loadTable = () => onChanged()

  const dropColumn = async (column: string) => {
    if (!window.confirm(`Drop column "${column}" from "${table.name}"?`)) return
    setDeleting(column)
    try {
      await api.dropColumn(connection.id, table.name, column)
      toast(`Dropped column "${column}"`, 'success')
      loadTable()
    } catch (err) {
      toast((err as Error).message, 'error')
    } finally {
      setDeleting(null)
    }
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-semibold">{table.name}</h2>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => setAddColOpen(true)}>
            <Plus className="size-4" /> Add column
          </Button>
          <Button size="sm" onClick={() => setRowEditor({ open: true, mode: 'create' })}>
            <Plus className="size-4" /> Insert row
          </Button>
        </div>
      </div>

      <Tabs value={tab} onValueChange={setTab} defaultValue="columns">
        <TabsList>
          <TabsTrigger value="columns">Columns</TabsTrigger>
          <TabsTrigger value="rows">Rows</TabsTrigger>
          <TabsTrigger value="relationships">Relationships</TabsTrigger>
          <TabsTrigger value="indexes">Indexes</TabsTrigger>
          <TabsTrigger value="sql">SQL</TabsTrigger>
        </TabsList>
        <TabsContent value="columns">
          <div className="overflow-x-auto rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>PK</TableHead>
                  <TableHead>Nullable</TableHead>
                  <TableHead>Unique</TableHead>
                  <TableHead>Default</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {table.columns.map((col) => (
                  <TableRow key={col.name}>
                    <TableCell className="font-medium">
                      <span className="flex items-center gap-1.5">
                        {col.name}
                        {col.primary_key && <KeyRound className="size-3.5 text-amber-500" />}
                      </span>
                    </TableCell>
                    <TableCell className="text-muted-foreground">{col.data_type}</TableCell>
                    <TableCell>{col.primary_key ? <Badge>PK</Badge> : <span className="text-muted-foreground">—</span>}</TableCell>
                    <TableCell>{col.nullable ? 'yes' : 'no'}</TableCell>
                    <TableCell>{col.unique ? 'yes' : 'no'}</TableCell>
                    <TableCell className="font-mono text-xs">{col.default ?? '—'}</TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-8 text-muted-foreground hover:text-destructive"
                        disabled={deleting === col.name}
                        onClick={() => dropColumn(col.name)}
                      >
                        <Trash2 className="size-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </TabsContent>
<TabsContent value="rows">
            <RowsTable
              connection={connection}
              table={table}
              onEdit={(row, pk) => setRowEditor({ open: true, mode: 'edit', row, pk })}
            />
          </TabsContent>
          <TabsContent value="relationships">
            {onNavigate ? (
              <RelationshipsPanel
                connection={connection}
                table={table}
                onChanged={loadTable}
                onNavigate={onNavigate}
              />
            ) : (
              <p className="text-sm text-muted-foreground">No navigation available.</p>
            )}
          </TabsContent>
        <TabsContent value="indexes">
          <IndexesPanel connection={connection} table={table} onChanged={loadTable} />
        </TabsContent>
        <TabsContent value="sql">
          <SqlView connectionId={connection.id} tableName={table.name} />
        </TabsContent>
      </Tabs>

      <AddColumnDialog
        open={addColOpen}
        connId={connection.id}
        tableName={table.name}
        onClose={() => setAddColOpen(false)}
        onAdded={() => {
          setAddColOpen(false)
          loadTable()
        }}
      />

      <RowEditorDialog
        open={rowEditor.open}
        connId={connection.id}
        table={table}
        mode={rowEditor.mode}
        row={rowEditor.mode === 'edit' ? rowEditor.row : undefined}
        pk={rowEditor.mode === 'edit' ? rowEditor.pk : undefined}
        onClose={() => setRowEditor((r) => ({ ...r, open: false }))}
        onDone={() => {
          setRowEditor((r) => ({ ...r, open: false }))
          loadTable()
        }}
      />
    </div>
  )
}

function RowsTable({
  connection,
  table,
  onEdit,
}: {
  connection: Connection
  table: TableInfo
  onEdit: (row: Record<string, unknown>, pk: Record<string, unknown>) => void
}) {
  const [data, setData] = useState<{ columns: string[]; rows: Record<string, unknown>[] } | null>(null)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('')
  const [sort, setSort] = useState<{ col: string; dir: 'asc' | 'desc' } | null>(null)
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(25)
  const [selected, setSelected] = useState<Set<number>>(new Set())

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setData(await api.listRows(connection.id, table.name))
    } catch (err) {
      toast((err as Error).message, 'error')
    } finally {
      setLoading(false)
    }
  }, [connection.id, table.name])

  useEffect(() => {
    load()
  }, [load])

  const pkCols = table.columns.filter((c) => c.primary_key).map((c) => c.name)

  const rows = data?.rows ?? []

  const visible = useMemo(() => {
    let out = rows
    if (filter.trim()) {
      const q = filter.trim().toLowerCase()
      out = out.filter((row) =>
        Object.values(row).some((v) => String(v ?? '').toLowerCase().includes(q))
      )
    }
    if (sort) {
      const { col, dir } = sort
      const mul = dir === 'asc' ? 1 : -1
      out = [...out].sort((a, b) => {
        const av = a[col]
        const bv = b[col]
        if (av === null || av === undefined) return mul
        if (bv === null || bv === undefined) return -mul
        if (typeof av === 'number' && typeof bv === 'number') return (av - bv) * mul
        return String(av).localeCompare(String(bv), undefined, { numeric: true }) * mul
      })
    }
    return out
  }, [rows, filter, sort])

  const pageCount = Math.max(1, Math.ceil(visible.length / pageSize))
  const safePage = Math.min(page, pageCount - 1)
  const pageRows = visible.slice(safePage * pageSize, safePage * pageSize + pageSize)

  useEffect(() => setSelected(new Set()), [filter, sort, pageSize])
  useEffect(() => setPage(0), [filter, sort, pageSize])

  const toggleSort = (col: string) =>
    setSort((s) => (s?.col === col ? (s.dir === 'asc' ? { col, dir: 'desc' } : null) : { col, dir: 'asc' }))

  const toggleSelect = (idx: number) =>
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(idx)) next.delete(idx)
      else next.add(idx)
      return next
    })

  const allPageSelected =
    pageRows.length > 0 && pageRows.every((_, i) => selected.has(safePage * pageSize + i))

  const toggleSelectPage = () => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (allPageSelected) {
        pageRows.forEach((_, i) => next.delete(safePage * pageSize + i))
      } else {
        pageRows.forEach((_, i) => next.add(safePage * pageSize + i))
      }
      return next
    })
  }

  const removeRows = async (pks: Record<string, unknown>[]) => {
    if (!pks.length) return
    if (!window.confirm(`Delete ${pks.length} selected row(s)?`)) return
    try {
      for (const pk of pks) {
        await api.deleteRow(connection.id, table.name, { data: {}, pk })
      }
      toast(`Deleted ${pks.length} row(s)`, 'success')
      setSelected(new Set())
      load()
    } catch (err) {
      toast((err as Error).message, 'error')
    }
  }

  const removeRow = async (pk: Record<string, unknown>) => {
    if (!window.confirm('Delete this row?')) return
    try {
      await api.deleteRow(connection.id, table.name, { data: {}, pk })
      toast('Row deleted', 'success')
      load()
    } catch (err) {
      toast((err as Error).message, 'error')
    }
  }

  const pkOf = (row: Record<string, unknown>) =>
    Object.fromEntries(Object.entries(row).filter(([k]) => pkCols.includes(k)))

  const exportCsv = () => {
    if (!data) return
    const cells = (values: unknown[]) => values.map((v) => `"${String(v ?? '').replaceAll('"', '""')}"`).join(',')
    const csv = [data.columns.join(','), ...visible.map((r) => cells(data.columns.map((c) => r[c])))].join('\n')
    downloadFile(`${table.name}.csv`, csv, 'text/csv')
  }

  const exportJson = () => {
    if (!data) return
    const out = visible.map((r) => Object.fromEntries(data.columns.map((c) => [c, r[c] ?? null])))
    downloadFile(`${table.name}.json`, JSON.stringify(out, null, 2), 'application/json')
  }

  if (loading) return <p className="py-8 text-center text-sm text-muted-foreground">Loading…</p>
  if (!data || data.rows.length === 0)
    return <p className="py-8 text-center text-sm text-muted-foreground">No rows yet.</p>

  const sortIcon = (col: string) => {
    if (sort?.col !== col) return <ArrowUpDown className="size-3.5 opacity-40" />
    return sort.dir === 'asc' ? <ArrowUp className="size-3.5" /> : <ArrowDown className="size-3.5" />
  }

  return (
    <div className="grid gap-3">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative flex-1 min-w-40">
          <Search className="absolute top-1/2 left-2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder={`Filter ${visible.length} of ${data.rows.length} rows…`}
            className="pl-8"
          />
        </div>
        {selected.size > 0 && pkCols.length > 0 && (
          <Button
            variant="destructive"
            size="sm"
            onClick={() =>
              removeRows([...selected].map((i) => pkOf(visible[i])).filter((p) => Object.keys(p).length > 0))
            }
          >
            <Trash2 className="size-4" /> Delete {selected.size} selected
          </Button>
        )}
        <div className="ml-auto flex gap-1.5">
          <Button variant="outline" size="sm" onClick={exportCsv}>
            <Download className="size-4" /> CSV
          </Button>
          <Button variant="outline" size="sm" onClick={exportJson}>
            <Download className="size-4" /> JSON
          </Button>
        </div>
      </div>

      {visible.length === 0 ? (
        <p className="py-8 text-center text-sm text-muted-foreground">No rows match the filter.</p>
      ) : (
        <div className="overflow-x-auto rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-8">
                  <input
                    type="checkbox"
                    className="size-4"
                    checked={allPageSelected}
                    onChange={toggleSelectPage}
                  />
                </TableHead>
                {data.columns.map((col) => (
                  <TableHead key={col}>
                    <button
                      className="flex items-center gap-1 hover:text-foreground"
                      onClick={() => toggleSort(col)}
                      title={`Sort by ${col}`}
                    >
                      {col}
                      {sortIcon(col)}
                    </button>
                  </TableHead>
                ))}
                <TableHead className="w-16 text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {pageRows.map((row, i) => {
                const idx = safePage * pageSize + i
                const pk = pkOf(row)
                return (
                  <TableRow key={idx} className={selected.has(idx) ? 'bg-accent/50' : ''}>
                    <TableCell>
                      <input
                        type="checkbox"
                        className="size-4"
                        checked={selected.has(idx)}
                        onChange={() => toggleSelect(idx)}
                      />
                    </TableCell>
                    {data.columns.map((col) => (
                      <TableCell key={col} className="font-mono text-xs">
                        {String(row[col] ?? '')}
                      </TableCell>
                    ))}
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        {pkCols.length > 0 && (
                          <>
                            <Button variant="ghost" size="icon" className="size-8" onClick={() => onEdit(row, pk)}>
                              <Pencil className="size-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="size-8 text-muted-foreground hover:text-destructive"
                              onClick={() => removeRow(pk)}
                            >
                              <Trash2 className="size-4" />
                            </Button>
                          </>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Pagination */}
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>
          {visible.length} row(s)
          {selected.size > 0 && ` · ${selected.size} selected`}
        </span>
        <div className="flex items-center gap-2">
          <Select
            value={String(pageSize)}
            onValueChange={(v) => setPageSize(Number(v))}
          >
            <SelectTrigger size="sm" className="h-7 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {[10, 25, 50, 100].map((n) => (
                <SelectItem key={n} value={String(n)}>
                  {n} / page
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <div className="flex items-center gap-1">
            <Button
              variant="outline"
              size="icon"
              className="size-7"
              disabled={safePage === 0}
              onClick={() => setPage((p) => Math.max(0, p - 1))}
            >
              ‹
            </Button>
            <span className="min-w-16 text-center">
              {safePage + 1} / {pageCount}
            </span>
            <Button
              variant="outline"
              size="icon"
              className="size-7"
              disabled={safePage >= pageCount - 1}
              onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
            >
              ›
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

function downloadFile(filename: string, content: string, type: string) {
  const blob = new Blob([content], { type })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function SqlView({ connectionId, tableName }: { connectionId: string; tableName: string }) {
  const [sql, setSql] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .tableSql(connectionId, tableName)
      .then((g) => setSql(g.sql))
      .catch((err) => setError((err as Error).message))
  }, [connectionId, tableName])

  const copy = async () => {
    if (!sql) return
    try {
      await navigator.clipboard.writeText(sql)
      toast('SQL copied', 'success')
    } catch {
      toast('Copy failed', 'error')
    }
  }

  if (error) return <p className="py-8 text-center text-sm text-destructive">{error}</p>
  if (sql === null) return <p className="py-8 text-center text-sm text-muted-foreground">Loading…</p>

  return (
    <div className="grid gap-2">
      <div className="flex justify-end">
        <Button variant="outline" size="sm" onClick={copy}>
          <Copy className="size-4" /> Copy
        </Button>
      </div>
      <pre className="overflow-x-auto rounded-md border bg-muted/40 p-4 font-mono text-xs leading-relaxed">
        {sql}
      </pre>
    </div>
  )
}

function AddColumnDialog({
  open,
  connId,
  tableName,
  onClose,
  onAdded,
}: {
  open: boolean
  connId: string
  tableName: string
  onClose: () => void
  onAdded: () => void
}) {
  const [col, setCol] = useState<ColumnDef>({ name: '', data_type: 'TEXT', nullable: true })
  const [busy, setBusy] = useState(false)

  const submit = async () => {
    if (!col.name.trim()) return
    setBusy(true)
    try {
      await api.addColumn(connId, tableName, { ...col, name: col.name.trim() })
      toast('Column added', 'success')
      onAdded()
    } catch (err) {
      toast((err as Error).message, 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>Add column to {tableName}</DialogTitle>
          <DialogDescription>SQL: ALTER TABLE {tableName} ADD COLUMN …</DialogDescription>
        </DialogHeader>
        <div className="grid gap-3">
          <div className="grid gap-1.5">
            <Label>Name</Label>
            <Input value={col.name} placeholder="column_name" onChange={(e) => setCol((c) => ({ ...c, name: e.target.value }))} />
          </div>
          <div className="grid gap-1.5">
            <Label>Type</Label>
            <Select value={col.data_type} onValueChange={(v) => setCol((c) => ({ ...c, data_type: v }))}>
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PORTABLE_TYPES.map((t) => (
                  <SelectItem key={t} value={t}>
                    {t}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-center gap-4">
            <label className="flex cursor-pointer items-center gap-2 text-sm">
              <input
                type="checkbox"
                className="size-4"
                checked={col.primary_key ?? false}
                onChange={(e) => setCol((c) => ({ ...c, primary_key: e.target.checked }))}
              />
              Primary key
            </label>
            <label className="flex cursor-pointer items-center gap-2 text-sm">
              <input
                type="checkbox"
                className="size-4"
                checked={col.nullable ?? true}
                onChange={(e) => setCol((c) => ({ ...c, nullable: e.target.checked }))}
              />
              Nullable
            </label>
            <label className="flex cursor-pointer items-center gap-2 text-sm">
              <input
                type="checkbox"
                className="size-4"
                checked={col.unique ?? false}
                onChange={(e) => setCol((c) => ({ ...c, unique: e.target.checked }))}
              />
              Unique
            </label>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={busy || !col.name.trim()}>
            {busy ? 'Adding…' : 'Add column'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function IndexesPanel({
  connection,
  table,
  onChanged,
}: {
  connection: Connection
  table: TableInfo
  onChanged: () => void
}) {
  const [indexes, setIndexes] = useState<IndexInfo[] | null>(null)
  const [createOpen, setCreateOpen] = useState(false)

  const load = useCallback(async () => {
    try {
      setIndexes(await api.listIndexes(connection.id, table.name))
    } catch (err) {
      toast((err as Error).message, 'error')
    }
  }, [connection.id, table.name])

  useEffect(() => {
    load()
  }, [load])

  const dropIndex = async (name: string) => {
    if (!window.confirm(`Drop index "${name}"?`)) return
    try {
      await api.dropIndex(connection.id, table.name, name)
      toast(`Dropped index "${name}"`, 'success')
      load()
    } catch (err) {
      toast((err as Error).message, 'error')
    }
  }

  return (
    <div className="grid gap-3">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {indexes ? `${indexes.length} index(es) on ${table.name}` : 'Loading…'}
        </p>
        <Button variant="outline" size="sm" onClick={() => setCreateOpen(true)}>
          <Plus className="size-4" /> Create index
        </Button>
      </div>
      {indexes && indexes.length > 0 ? (
        <div className="overflow-x-auto rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Columns</TableHead>
                <TableHead>Type</TableHead>
                <TableHead className="w-16 text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {indexes.map((idx) => (
                <TableRow key={idx.name}>
                  <TableCell className="font-mono text-xs">{idx.name}</TableCell>
                  <TableCell className="font-mono text-xs">
                    {idx.columns.join(', ')}
                  </TableCell>
                  <TableCell>
                    {idx.unique ? <Badge variant="outline">UNIQUE</Badge> : <Badge variant="secondary">regular</Badge>}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-8 text-muted-foreground hover:text-destructive"
                      onClick={() => dropIndex(idx.name)}
                      title="Drop index"
                    >
                      <Trash2 className="size-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ) : (
        <p className="py-6 text-center text-sm text-muted-foreground">
          No indexes. Create one to speed up lookups.
        </p>
      )}

      {createOpen && (
        <CreateIndexDialog
          connection={connection}
          table={table}
          onClose={() => setCreateOpen(false)}
          onCreated={() => {
            setCreateOpen(false)
            load()
            onChanged()
          }}
        />
      )}
    </div>
  )
}

function CreateIndexDialog({
  connection,
  table,
  onClose,
  onCreated,
}: {
  connection: Connection
  table: TableInfo
  onClose: () => void
  onCreated: () => void
}) {
  const available = table.columns.filter((c) => !c.primary_key).map((c) => c.name)
  const [name, setName] = useState('')
  const [cols, setCols] = useState<string[]>([])
  const [unique, setUnique] = useState(false)
  const [busy, setBusy] = useState(false)

  const submit = async () => {
    if (!name.trim() || cols.length === 0) return
    setBusy(true)
    try {
      await api.createIndex(connection.id, table.name, {
        name: name.trim(),
        columns: cols,
        unique,
      } satisfies IndexCreate)
      toast('Index created', 'success')
      onCreated()
    } catch (err) {
      toast((err as Error).message, 'error')
      setBusy(false)
    }
  }

  const toggleCol = (c: string) =>
    setCols((prev) => (prev.includes(c) ? prev.filter((x) => x !== c) : [...prev, c]))

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create index</DialogTitle>
          <DialogDescription>
            Index on {table.name}. Covered columns are combined into a single index.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4">
          <div className="grid gap-1.5">
            <Label>Index name</Label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={`idx_${table.name}_…`}
            />
          </div>
          <div className="grid gap-1.5">
            <Label>Columns</Label>
            {available.length === 0 ? (
              <p className="text-xs text-muted-foreground">No indexable (non-primary) columns.</p>
            ) : (
              <div className="flex flex-wrap gap-1.5">
                {available.map((c) => (
                  <Button
                    key={c}
                    type="button"
                    variant={cols.includes(c) ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => toggleCol(c)}
                  >
                    {c}
                  </Button>
                ))}
              </div>
            )}
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              className="size-4"
              checked={unique}
              onChange={(e) => setUnique(e.target.checked)}
            />
            Unique index
          </label>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={busy || !name.trim() || cols.length === 0}>
            {busy ? 'Creating…' : 'Create index'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}