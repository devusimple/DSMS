import { useState } from 'react'

import { api } from '@/lib/api'
import type { Connection, ConnectionCreate, Dialect } from '@/lib/types'
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

const EMPTY: ConnectionCreate = {
  name: '',
  dialect: 'sqlite',
  host: '',
  port: 5432,
  database: '',
  username: '',
  password: '',
  file: '',
}

export function CreateConnectionDialog({
  open,
  onClose,
  onCreate,
}: {
  open: boolean
  onClose: () => void
  onCreate: (conn: Connection) => void
}) {
  const [form, setForm] = useState<ConnectionCreate>(EMPTY)
  const [busy, setBusy] = useState(false)

  const set = <K extends keyof ConnectionCreate>(key: K, value: ConnectionCreate[K]) =>
    setForm((f) => ({ ...f, [key]: value }))

  const handleDialect = (value: string) => {
    const dialect = value as Dialect
    setForm((f) => ({ ...f, dialect, port: dialect === 'mysql' ? 3306 : 5432 }))
  }

  const submit = async () => {
    setBusy(true)
    try {
      const payload: ConnectionCreate = { name: form.name.trim(), dialect: form.dialect }
      if (form.dialect === 'sqlite') {
        payload.file = form.file?.trim() || undefined
      } else {
        payload.host = form.host?.trim() || undefined
        payload.database = form.database?.trim() || undefined
        payload.username = form.username?.trim() || undefined
        payload.password = form.password || undefined
        payload.port = form.port || undefined
      }
      const conn = await api.createConnection(payload)
      toast(`Connected to "${conn.name}"`, 'success')
      onCreate(conn)
      setForm(EMPTY)
    } catch (err) {
      toast((err as Error).message, 'error')
    } finally {
      setBusy(false)
    }
  }

  const isSqlite = form.dialect === 'sqlite'

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>New connection</DialogTitle>
          <DialogDescription>
            Connection details are kept in memory only — nothing is persisted.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5">
              <Label htmlFor="conn-name">Name</Label>
              <Input
                id="conn-name"
                value={form.name}
                placeholder="My app database"
                onChange={(e) => set('name', e.target.value)}
              />
            </div>
            <div className="grid gap-1.5">
              <Label>Dialect</Label>
              <Select value={form.dialect} onValueChange={handleDialect}>
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="sqlite">SQLite</SelectItem>
                  <SelectItem value="postgresql">PostgreSQL</SelectItem>
                  <SelectItem value="mysql">MySQL</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {isSqlite ? (
            <div className="grid gap-1.5">
              <Label htmlFor="conn-file">Database file</Label>
              <Input
                id="conn-file"
                value={form.file ?? ''}
                placeholder={'Leave empty for in-memory (:memory:)'}
                onChange={(e) => set('file', e.target.value)}
              />
            </div>
          ) : (
            <>
              <div className="grid grid-cols-3 gap-3">
                <div className="col-span-2 grid gap-1.5">
                  <Label htmlFor="conn-host">Host</Label>
                  <Input
                    id="conn-host"
                    value={form.host ?? ''}
                    placeholder="localhost"
                    onChange={(e) => set('host', e.target.value)}
                  />
                </div>
                <div className="grid gap-1.5">
                  <Label htmlFor="conn-port">Port</Label>
                  <Input
                    id="conn-port"
                    type="number"
                    value={form.port ?? ''}
                    onChange={(e) => set('port', Number(e.target.value))}
                  />
                </div>
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="conn-db">Database</Label>
                <Input
                  id="conn-db"
                  value={form.database ?? ''}
                  placeholder="database name"
                  onChange={(e) => set('database', e.target.value)}
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="grid gap-1.5">
                  <Label htmlFor="conn-user">Username</Label>
                  <Input
                    id="conn-user"
                    value={form.username ?? ''}
                    autoComplete="off"
                    onChange={(e) => set('username', e.target.value)}
                  />
                </div>
                <div className="grid gap-1.5">
                  <Label htmlFor="conn-pass">Password</Label>
                  <Input
                    id="conn-pass"
                    type="password"
                    value={form.password ?? ''}
                    autoComplete="new-password"
                    onChange={(e) => set('password', e.target.value)}
                  />
                </div>
              </div>
            </>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={busy || !form.name.trim()}>
            {busy ? 'Connecting…' : 'Connect'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}