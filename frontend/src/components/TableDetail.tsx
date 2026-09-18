import { useCallback, useEffect, useState } from 'react'
import { Copy, KeyRound, Pencil, Plus, Trash2 } from 'lucide-react'

import { api } from '@/lib/api'
import type { ColumnDef, Connection, TableInfo } from '@/lib/types'
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

export function TableDetail({
  connection,
  table,
  onChanged,
}: {
  connection: Connection
  table: TableInfo
  onChanged: () => void
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

  if (loading) return <p className="py-8 text-center text-sm text-muted-foreground">Loading…</p>
  if (!data || data.rows.length === 0)
    return <p className="py-8 text-center text-sm text-muted-foreground">No rows yet.</p>

  const pkCols = table.columns.filter((c) => c.primary_key).map((c) => c.name)

  return (
    <div className="overflow-x-auto rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            {data.columns.map((col) => (
              <TableHead key={col}>{col}</TableHead>
            ))}
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.rows.map((row, i) => {
            const pk = Object.fromEntries(
              Object.entries(row).filter(([k]) => pkCols.includes(k))
            )
            return (
              <TableRow key={i}>
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
  )
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