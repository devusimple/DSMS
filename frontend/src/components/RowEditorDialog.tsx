import { useEffect, useState } from 'react'

import { api } from '@/lib/api'
import type { TableInfo } from '@/lib/types'
import { toast } from '@/components/toaster'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

function parseValue(raw: string): unknown {
  const v = raw.trim()
  if (v === '') return null
  if (v === 'null') return null
  if (v === 'true') return true
  if (v === 'false') return false
  if (/^-?\d+$/.test(v)) return Number(v)
  if (/^-?\d*\.\d+$/.test(v)) return Number(v)
  return raw
}

export function RowEditorDialog({
  open,
  connId,
  table,
  mode,
  row,
  pk,
  onClose,
  onDone,
}: {
  open: boolean
  connId: string
  table: TableInfo
  mode: 'create' | 'edit'
  row?: Record<string, unknown>
  pk?: Record<string, unknown>
  onClose: () => void
  onDone: () => void
}) {
  const [values, setValues] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    const initial: Record<string, string> = {}
    for (const col of table.columns) {
      if (mode === 'edit' && row) {
        const v = row[col.name]
        initial[col.name] = v === null || v === undefined ? 'null' : String(v)
      } else {
        initial[col.name] = ''
      }
    }
    setValues(initial)
  }, [open, mode, row, table])

  if (!open) return null

  const isEdit = mode === 'edit'

  const submit = async () => {
    setBusy(true)
    try {
      const data: Record<string, unknown> = {}
      for (const col of table.columns) {
        data[col.name] = parseValue(values[col.name] ?? '')
      }
      if (isEdit) {
        if (!pk) throw new Error('Missing primary key for update.')
        await api.updateRow(connId, table.name, { data, pk })
        toast('Row updated', 'success')
      } else {
        await api.insertRow(connId, table.name, { data })
        toast('Row inserted', 'success')
      }
      onDone()
    } catch (err) {
      toast((err as Error).message, 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{isEdit ? `Edit row in ${table.name}` : `Insert row into ${table.name}`}</DialogTitle>
          <DialogDescription>
            Empty values become NULL. Type control keywords null, true, false and numbers.
          </DialogDescription>
        </DialogHeader>
        <div className="max-h-[60vh] overflow-y-auto">
          <div className="grid gap-3">
            {table.columns.map((col) => (
              <div key={col.name} className="grid gap-1.5">
                <Label className="flex items-center gap-2">
                  <span className="font-mono text-xs">{col.name}</span>
                  <span className="text-xs font-normal text-muted-foreground">
                    {col.data_type}
                    {col.primary_key ? ' · PK' : ''}
                  </span>
                </Label>
                <Input
                  value={values[col.name] ?? ''}
                  placeholder={col.primary_key ? 'primary key value' : 'null'}
                  onChange={(e) => setValues((v) => ({ ...v, [col.name]: e.target.value }))}
                />
              </div>
            ))}
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={busy}>
            {busy ? 'Saving…' : isEdit ? 'Update row' : 'Insert row'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}