import { useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'

import { api } from '@/lib/api'
import type { ColumnDef, TableInfo } from '@/lib/types'
import { PORTABLE_TYPES } from '@/lib/types_constants'
import { toast } from '@/components/toaster'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { cn } from '@/lib/utils'

interface RowDraft extends ColumnDef {
  key: number
}

const AUTO_DEFAULT: ColumnDef[] = [
  { name: '_id', data_type: 'INTEGER', primary_key: true, nullable: false },
  { name: 'created_at', data_type: 'DATETIME', nullable: false, default: 'CURRENT_TIMESTAMP' },
  { name: 'updated_at', data_type: 'DATETIME', nullable: false, default: 'CURRENT_TIMESTAMP' },
]

export function CreateTableDialog({
  open,
  connId,
  onClose,
  onCreated,
}: {
  open: boolean
  connId: string
  onClose: () => void
  onCreated: (table: TableInfo) => void
}) {
  const [name, setName] = useState('')
  const [rows, setRows] = useState<RowDraft[]>([emptyRow(0)])
  const [autoCols, setAutoCols] = useState<ColumnDef[]>(AUTO_DEFAULT)
  const [busy, setBusy] = useState(false)

  const update = (key: number, patch: Partial<RowDraft>) =>
    setRows((rs) => rs.map((r) => (r.key === key ? { ...r, ...patch } : r)))

  const hasUserPk = rows.some((r) => r.primary_key)

  const submit = async () => {
    if (!name.trim()) return
    setBusy(true)
    try {
      const userCols = rows.map(({ key: _key, ...col }) => col)
      const finalAuto = hasUserPk ? autoCols.filter((c) => c.name !== '_id') : autoCols
      const submitted = [...finalAuto, ...userCols]
      const submittedNames = new Set(submitted.map((c) => c.name))
      const excludeAuto = AUTO_DEFAULT.map((c) => c.name).filter((n) => !submittedNames.has(n))
      const table = await api.createTable(connId, {
        name: name.trim(),
        columns: submitted,
        exclude_auto: excludeAuto,
      })
      toast(`Table "${table.name}" created`, 'success')
      onCreated(table)
      setName('')
      setRows([emptyRow(0)])
      setAutoCols(AUTO_DEFAULT)
    } catch (err) {
      toast((err as Error).message, 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Create table</DialogTitle>
          <DialogDescription>Define the table name and its columns.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-1.5">
          <Label htmlFor="table-name">Table name</Label>
          <Input
            id="table-name"
            value={name}
            placeholder="users"
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <div className="grid gap-2">
          <div className="grid grid-cols-[1fr_140px_80px_80px_40px] items-center gap-2 px-1 text-xs font-medium text-muted-foreground">
            <span>Name</span>
            <span>Type</span>
            <span className="text-center">PK</span>
            <span className="text-center">Nullable</span>
            <span />
          </div>
          {autoCols.map((col) => {
            const locked = col.name === '_id'
            const replaced = locked && hasUserPk
            return (
              <div
                key={col.name}
                className={cn(
                  'grid grid-cols-[1fr_140px_80px_80px_40px] items-center gap-2',
                  replaced && 'opacity-50'
                )}
                title={replaced ? 'Replaced by your primary key — will not be created.' : undefined}
              >
                <Input value={col.name} disabled readOnly />
                <Select value={col.data_type} disabled>
                  <SelectTrigger>
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
                <input
                  type="checkbox"
                  disabled
                  className="mx-auto size-4"
                  checked={col.primary_key ?? false}
                />
                <input
                  type="checkbox"
                  disabled
                  className="mx-auto size-4"
                  checked={col.nullable !== false}
                />
                {locked ? (
                  <span />
                ) : (
                  <Button
                    variant="ghost"
                    size="icon"
                    className="size-8"
                    title="Remove this column"
                    onClick={() => setAutoCols((prev) => prev.filter((c) => c.name !== col.name))}
                  >
                    <Trash2 className="size-4" />
                  </Button>
                )}
              </div>
            )
          })}
          {rows.map((row, i) => (
            <div key={row.key} className="grid grid-cols-[1fr_140px_80px_80px_40px] items-center gap-2">
              <Input
                value={row.name}
                placeholder={`column_${i + 1}`}
                onChange={(e) => update(row.key, { name: e.target.value })}
              />
              <Select
                value={row.data_type}
                onValueChange={(v) => update(row.key, { data_type: v })}
              >
                <SelectTrigger>
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
              <input
                type="checkbox"
                className="mx-auto size-4"
                checked={row.primary_key ?? false}
                onChange={(e) => update(row.key, { primary_key: e.target.checked })}
              />
              <input
                type="checkbox"
                className="mx-auto size-4"
                checked={row.nullable ?? true}
                onChange={(e) => update(row.key, { nullable: e.target.checked })}
              />
              <Button
                variant="ghost"
                size="icon"
                className="size-8"
                disabled={rows.length === 1}
                onClick={() => setRows((rs) => rs.filter((r) => r.key !== row.key))}
              >
                <Trash2 className="size-4" />
              </Button>
            </div>
          ))}
          <Button
            variant="outline"
            size="sm"
            onClick={() => setRows((rs) => [...rs, emptyRow(Math.max(...rs.map((r) => r.key)) + 1)])}
          >
            <Plus className="size-4" /> Add column
          </Button>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={busy || !name.trim()}>
            {busy ? 'Creating…' : 'Create table'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function emptyRow(key: number): RowDraft {
  return { key, name: '', data_type: 'TEXT', nullable: true }
}