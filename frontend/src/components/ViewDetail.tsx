import { useCallback, useEffect, useState } from 'react'
import { Eye, EyeOff } from 'lucide-react'

import { api } from '@/lib/api'
import { toast } from '@/components/toaster'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'

export function ViewDetail({
  connectionId,
  viewName,
}: {
  connectionId: string
  viewName: string
}) {
  const [data, setData] = useState<{ columns: string[]; rows: Record<string, unknown>[] } | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setData(await api.viewRows(connectionId, viewName))
    } catch (err) {
      toast((err as Error).message, 'error')
    } finally {
      setLoading(false)
    }
  }, [connectionId, viewName])

  useEffect(() => {
    load()
  }, [load])

  if (loading)
    return <p className="py-8 text-center text-sm text-muted-foreground">Loading…</p>
  if (!data || data.rows.length === 0)
    return (
      <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
        <EyeOff className="size-8 opacity-40" />
        <p className="mt-2 text-sm">No rows returned.</p>
      </div>
    )

  return (
    <div className="grid gap-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Eye className="size-4 text-muted-foreground" />
          <h2 className="font-semibold">View {viewName}</h2>
        </div>
        <Button variant="outline" size="sm" onClick={load} disabled={loading}>
          Refresh
        </Button>
      </div>
      <p className="text-xs text-muted-foreground">
        {data.rows.length} row(s) returned (max 1 000).
      </p>
      <div className="overflow-x-auto rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              {data.columns.map((col) => (
                <TableHead key={col}>{col}</TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.rows.map((row, i) => (
              <TableRow key={i}>
                {data.columns.map((col) => (
                  <TableCell key={col} className="font-mono text-xs">
                    {String(row[col] ?? '')}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}