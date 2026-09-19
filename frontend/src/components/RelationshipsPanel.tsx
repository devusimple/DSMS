import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link2, Plus, Unlink, Workflow } from 'lucide-react'

import { api } from '@/lib/api'
import type {
  Cardinality,
  Connection,
  ForeignKeyCreate,
  TableInfo,
  TableRelationships,
} from '@/lib/types'
import { FK_ACTIONS } from '@/lib/types'
import { toast } from '@/components/toaster'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

export function RelationshipsPanel({
  connection,
  table,
  onChanged,
  onNavigate,
}: {
  connection: Connection
  table: TableInfo
  onChanged: () => void
  onNavigate: (tableName: string) => void
}) {
  const [rel, setRel] = useState<TableRelationships | null>(null)
  const [createOpen, setCreateOpen] = useState(false)

  const load = useCallback(async () => {
    try {
      setRel(await api.listRelationships(connection.id, table.name))
    } catch (err) {
      toast((err as Error).message, 'error')
    }
  }, [connection.id, table.name])

  useEffect(() => {
    setRel(null)
    load()
  }, [load])

  const drop = async (fk: { name: string; table?: string; referred_table?: string }) => {
    const label = fk.table ? `${fk.table}.${fk.name}` : `${table.name}.${fk.name}`
    if (!window.confirm(`Drop foreign key "${label}"?`)) return
    try {
      await api.dropForeignKey(connection.id, table.name, fk.name)
      toast('Foreign key dropped', 'success')
      load()
      onChanged()
    } catch (err) {
      toast((err as Error).message, 'error')
    }
  }

  const count = (rel?.outbound.length ?? 0) + (rel?.inbound.length ?? 0)

  const TableLink = ({ name }: { name: string }) => (
    <button
      className="font-medium text-foreground underline decoration-muted-foreground/40 decoration-dotted underline-offset-2 hover:text-primary"
      onClick={() => onNavigate(name)}
    >
      {name}
    </button>
  )

  return (
    <div className="grid gap-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {rel ? `${count} constraint(s)` : 'Loading…'}
        </p>
        <Button variant="outline" size="sm" onClick={() => setCreateOpen(true)}>
          <Plus className="size-4" /> Add relationship
        </Button>
      </div>

      {!rel ? (
        <p className="py-6 text-center text-sm text-muted-foreground">Loading…</p>
      ) : (
        <>
          {rel.junction && (
            <div className="flex items-center gap-2 rounded-md border bg-muted/30 p-3 text-sm">
              <Workflow className="size-4 shrink-0 text-muted-foreground" />
              <span>
                <span className="font-medium">{table.name}</span> is a{' '}
                <Badge>M:N</Badge> junction linking{' '}
                {rel.many_to_many.map((m, i) => (
                  <span key={m.endpoint}>
                    {i > 0 && ' and '}
                    <TableLink name={m.endpoint} />
                  </span>
                ))}
                .
              </span>
            </div>
          )}

          {rel.many_to_many.length > 0 && !rel.junction && (
            <div className="flex flex-wrap items-center gap-2">
              {rel.many_to_many.map((m) => (
                <div
                  key={`${m.endpoint}-${m.through}`}
                  className="flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-sm"
                >
                  <TableLink name={table.name} />
                  <GoesTo />
                  <Badge>M:N</Badge>
                  <GoesTo />
                  <TableLink name={m.endpoint} />
                  <span className="text-xs text-muted-foreground">
                    via <span className="font-mono">{m.through}</span>
                  </span>
                </div>
              ))}
            </div>
          )}

          <div className="grid gap-3">
            <h3 className="text-xs font-medium text-muted-foreground">References (this table → other)</h3>
            {rel.outbound.length === 0 ? (
              <p className="text-sm text-muted-foreground">No outbound foreign keys.</p>
            ) : (
              rel.outbound.map((fk) => (
                <div key={fk.name} className="grid gap-1 rounded-md border p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-xs">{table.name}</span>
                    <span className="text-xs text-muted-foreground">
                      ({fk.columns.join(', ')})
                    </span>
                    <GoesTo />
                    <TableLink name={fk.referred_table} />
                    <span className="font-mono text-xs">
                      ({fk.referred_columns.join(', ')})
                    </span>
                    <CardBadge value={fk.cardinality} />
                    <div className="ml-auto flex items-center gap-1">
                      <span className="hidden font-mono text-[11px] text-muted-foreground sm:inline">
                        {fk.name}
                      </span>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-7 text-muted-foreground hover:text-destructive"
                        onClick={() => drop(fk)}
                        title="Drop foreign key"
                      >
                        <Unlink className="size-4" />
                      </Button>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-3 text-[11px] text-muted-foreground">
                    {fk.on_delete && <span>ON DELETE {fk.on_delete}</span>}
                    {fk.on_update && <span>ON UPDATE {fk.on_update}</span>}
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="grid gap-3">
            <h3 className="text-xs font-medium text-muted-foreground">Referenced by (other → this table)</h3>
            {rel.inbound.length === 0 ? (
              <p className="text-sm text-muted-foreground">No inbound foreign keys.</p>
            ) : (
              rel.inbound.map((fk) => (
                <div key={fk.name} className="grid gap-1 rounded-md border p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <TableLink name={fk.table} />
                    <span className="font-mono text-xs">({fk.columns.join(', ')})</span>
                    <GoesTo />
                    <span className="font-mono text-xs">{table.name}</span>
                    <span className="font-mono text-xs">
                      ({fk.referred_columns.join(', ')})
                    </span>
                    <CardBadge value={fk.cardinality} />
                    <div className="ml-auto flex items-center gap-1">
                      <span className="hidden font-mono text-[11px] text-muted-foreground sm:inline">
                        {fk.name}
                      </span>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-7 text-muted-foreground hover:text-destructive"
                        onClick={() => drop(fk)}
                        title="Drop foreign key"
                      >
                        <Unlink className="size-4" />
                      </Button>
                    </div>
                  </div>
                  <div className="flex gap-3 text-[11px] text-muted-foreground">
                    {fk.on_delete && <span>ON DELETE {fk.on_delete}</span>}
                    {fk.on_update && <span>ON UPDATE {fk.on_update}</span>}
                  </div>
                </div>
              ))
            )}
          </div>
        </>
      )}

      {createOpen && (
        <CreateForeignKeyDialog
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

function GoesTo() {
  return (
    <span className="text-muted-foreground">
      <Link2 className="size-3.5" />
    </span>
  )
}

function CardBadge({ value }: { value: Cardinality }) {
  return <Badge variant={value === '1:1' ? 'outline' : 'secondary'}>{value}</Badge>
}

function CreateForeignKeyDialog({
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
  const [tables, setTables] = useState<TableInfo[] | null>(null)
  const [name, setName] = useState('')
  const [localCols, setLocalCols] = useState<string[]>([])
  const [referredTable, setReferredTable] = useState('')
  const [onDelete, setOnDelete] = useState('')
  const [onUpdate, setOnUpdate] = useState('')
  const [busy, setBusy] = useState(false)

  const loadTables = useCallback(() => {
    api
      .listTables(connection.id)
      .then((list) => setTables(list.filter((t) => t.name !== table.name)))
      .catch((err) => toast((err as Error).message, 'error'))
  }, [connection.id, table.name])

  useEffect(() => {
    loadTables()
  }, [loadTables])

  const toggleLocal = (col: string) =>
    setLocalCols((prev) =>
      prev.includes(col) ? prev.filter((c) => c !== col) : [...prev, col]
    )

  const mapping = useMemo(() => {
    const ref = tables?.find((t) => t.name === referredTable)
    if (!ref) return []
    return localCols.map((col, i) => {
      const match = ref.columns.find((c) => c.name === col)
      return match ? match.name : (ref.columns[i]?.name ?? '')
    })
  }, [tables, referredTable, localCols])

  const complete = mapping.length > 0 && mapping.every((c) => c)

  const submit = async () => {
    if (!referredTable || !complete) return
    const body: ForeignKeyCreate = {
      columns: localCols,
      referred_table: referredTable,
      referred_columns: mapping,
      on_delete: onDelete,
      on_update: onUpdate,
    }
    if (name.trim()) body.name = name.trim()
    setBusy(true)
    try {
      await api.createForeignKey(connection.id, table.name, body)
      toast('Foreign key added', 'success')
      onCreated()
    } catch (err) {
      toast((err as Error).message, 'error')
      setBusy(false)
    }
  }

  const suggestedName = `fk_${table.name}_${referredTable}_${localCols.join('_')}`

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Add relationship</DialogTitle>
          <DialogDescription>
            A foreign key from {table.name} to a referenced table.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4">
          <div className="grid gap-1.5">
            <Label>Constraint name (optional)</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder={suggestedName} className="font-mono text-xs" />
          </div>

          <div className="grid gap-1.5">
            <Label>
              Columns in <span className="font-mono">{table.name}</span> (click in order)
            </Label>
            <div className="flex flex-wrap gap-1.5">
              {table.columns.map((c) => (
                <Button
                  key={c.name}
                  type="button"
                  variant={localCols.includes(c.name) ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => toggleLocal(c.name)}
                >
                  {localCols.includes(c.name) && (
                    <span className="mr-1 text-primary-foreground/60">
                      {localCols.indexOf(c.name) + 1}.
                    </span>
                  )}
                  {c.name}
                </Button>
              ))}
            </div>
          </div>

          <div className="grid gap-1.5">
            <Label>References table</Label>
            <Select value={referredTable} onValueChange={setReferredTable}>
              <SelectTrigger disabled={!tables}>
                <SelectValue placeholder={tables ? 'Select a table…' : 'Loading…'} />
              </SelectTrigger>
              <SelectContent>
                {(tables ?? []).map((t) => (
                  <SelectItem key={t.name} value={t.name}>
                    {t.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {mapping.length > 0 && (
            <div className="grid gap-1.5">
              <Label>Column mapping</Label>
              <div className="flex flex-wrap gap-1.5">
                {mapping.map((refCol, i) => (
                  <span
                    key={i}
                    className={cn(
                      'rounded-md border px-2 py-1 font-mono text-xs',
                      refCol ? 'border-foreground/20' : 'border-destructive/40 text-destructive'
                    )}
                  >
                    {localCols[i]} → {refCol || '??'}
                  </span>
                ))}
                {!complete && (
                  <span className="w-full text-[11px] text-destructive">
                    The referenced table lacks a matching column — add columns or pick another table.
                  </span>
                )}
              </div>
            </div>
          )}

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="grid gap-1.5">
              <Label>On delete</Label>
              <Select value={onDelete} onValueChange={setOnDelete}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <ActionItem value="" label="— no action —" />
                  {fkActions()}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <Label>On update</Label>
              <Select value={onUpdate} onValueChange={setOnUpdate}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <ActionItem value="" label="— no action —" />
                  {fkActions()}
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={busy || !referredTable || localCols.length === 0 || !complete}>
            {busy ? 'Adding…' : 'Add relationship'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function ActionItem({ value, label }: { value: string; label: string }) {
  return <SelectItem value={value}>{label}</SelectItem>
}

function fkActions() {
  return FK_ACTIONS.slice(1).map((a) => (
    <SelectItem key={a} value={a}>
      {a}
    </SelectItem>
  ))
}