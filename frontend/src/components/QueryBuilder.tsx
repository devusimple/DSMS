import { useCallback, useEffect, useState, type Dispatch, type SetStateAction } from 'react'
import { Loader2, Plus, Trash2, WandSparkles } from 'lucide-react'

import { api } from '@/lib/api'
import type { Connection, GenerateSqlRequest, TableInfo } from '@/lib/types'
import { toast } from '@/components/toaster'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

type Verb = GenerateSqlRequest['verb']

const VERBS: { value: Verb; label: string }[] = [
  { value: 'select', label: 'GET · SELECT' },
  { value: 'count', label: 'COUNT' },
  { value: 'insert', label: 'CREATE · INSERT' },
  { value: 'update', label: 'UPDATE' },
  { value: 'upsert', label: 'PUT · UPSERT' },
  { value: 'delete', label: 'DELETE' },
]

const WHERE_OPS = [
  'eq',
  'ne',
  'lt',
  'lte',
  'gt',
  'gte',
  'like',
  'ilike',
  'in',
  'not_in',
  'is_null',
  'is_not_null',
]

let rowId = 0
function nextId() {
  return rowId++
}

interface PairRow {
  id: number
  col: string
  value: string
}

interface WhereRow {
  id: number
  col: string
  op: string
  value: string
}

export function QueryBuilder({
  connection,
  onGenerated,
}: {
  connection: Connection
  onGenerated: (sql: string, params: Record<string, unknown> | null) => void
}) {
  const [tables, setTables] = useState<TableInfo[]>([])
  const [table, setTable] = useState('')
  const [verb, setVerb] = useState<Verb>('select')
  const [columns, setColumns] = useState('')
  const [distinct, setDistinct] = useState(false)
  const [search, setSearch] = useState('')
  const [searchColumns, setSearchColumns] = useState('')
  const [orderBy, setOrderBy] = useState('')
  const [orderDir, setOrderDir] = useState('asc')
  const [limit, setLimit] = useState('')
  const [offset, setOffset] = useState('')
  const [page, setPage] = useState('')
  const [pageSize, setPageSize] = useState('')
  const [eqRows, setEqRows] = useState<PairRow[]>([{ id: nextId(), col: '', value: '' }])
  const [whereRows, setWhereRows] = useState<WhereRow[]>([{ id: nextId(), col: '', op: 'eq', value: '' }])
  const [dataRows, setDataRows] = useState<PairRow[]>([{ id: nextId(), col: '', value: '' }])
  const [pkRows, setPkRows] = useState<PairRow[]>([{ id: nextId(), col: '', value: '' }])
  const [conflictColumns, setConflictColumns] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.listTables(connection.id).then(setTables).catch((err) => toast((err as Error).message, 'error'))
  }, [connection.id])

  const pickTable = (name: string) => {
    setTable(name)
    if (!columns.trim()) {
      const cols = tables.find((t) => t.name === name)?.columns.map((c) => c.name) ?? []
      if (cols.length) setColumns(cols.join(', '))
    }
  }

  const splitCols = (raw: string) =>
    raw
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)

  const pairsToObj = (rows: PairRow[]) =>
    Object.fromEntries(
      rows
        .map((r) => [r.col.trim(), coerce(r.value)])
        .filter(([c]) => c)
    )

  const intOrUndef = (raw: string) => {
    const n = Number(raw.trim())
    return raw.trim() === '' || Number.isNaN(n) ? undefined : n
  }

  const buildRequest = useCallback((): GenerateSqlRequest => {
    const base = { table, verb }
    const eq = pairsToObj(eqRows)
    const whereArr = whereRows
      .filter((r) => r.col.trim())
      .map((r): [string, string, unknown] => [r.col.trim(), r.op, coerce(r.value)])
    if (verb === 'select') {
      const req: GenerateSqlRequest = {
        ...base,
        distinct,
        eq: Object.keys(eq).length ? eq : undefined,
        where: whereArr.length ? whereArr : undefined,
      }
      if (search.trim()) {
        req.search = search.trim()
        req.search_columns = splitCols(searchColumns)
      }
      if (columns.trim()) req.columns = splitCols(columns)
      if (orderBy.trim()) {
        req.order_by = splitCols(orderBy)
        req.order_dir = orderDir
      }
      const l = intOrUndef(limit)
      const o = intOrUndef(offset)
      const p = intOrUndef(page)
      const ps = intOrUndef(pageSize)
      if (p !== undefined || ps !== undefined) {
        req.page = p
        req.page_size = ps
      } else if (l !== undefined || o !== undefined) {
        req.limit = l
        req.offset = o
      }
      return req
    }
    if (verb === 'count') {
      return {
        ...base,
        eq: Object.keys(eq).length ? eq : undefined,
        where: whereArr.length ? whereArr : undefined,
        ...(search.trim()
          ? { search: search.trim(), search_columns: splitCols(searchColumns) }
          : {}),
        ...(columns.trim() ? { columns: splitCols(columns) } : {}),
      }
    }
    const data = pairsToObj(dataRows)
    const pk = pairsToObj(pkRows)
    if (verb === 'insert') return { ...base, data }
    if (verb === 'upsert') {
      return { ...base, data, conflict_columns: splitCols(conflictColumns) }
    }
    if (verb === 'update') return { ...base, data, pk }
    return { ...base, pk }
  }, [table, verb, columns, distinct, search, searchColumns, orderBy, orderDir, limit, offset, page, pageSize, eqRows, whereRows, dataRows, pkRows, conflictColumns])

  const generate = async () => {
    if (!table.trim()) {
      toast('Pick a table first', 'error')
      return
    }
    setBusy(true)
    try {
      const res = await api.generateSql(connection.id, buildRequest())
      onGenerated(res.sql, Object.keys(res.params).length ? res.params : null)
    } catch (err) {
      toast((err as Error).message, 'error')
    } finally {
      setBusy(false)
    }
  }

  const updatePair = <T extends { id: number }>(
    rows: T[],
    setter: Dispatch<SetStateAction<T[]>>,
    id: number,
    patch: Partial<T>
  ) => setter(rows.map((r) => (r.id === id ? { ...r, ...patch } : r)))

  const sect = 'grid gap-1.5'
  const pairHeader = 'grid grid-cols-[1fr_1fr_28px] items-center gap-1.5'

  return (
    <div className="grid max-h-80 flex-none gap-3 overflow-y-auto rounded-md border p-3 text-xs">
      <div className="flex flex-wrap items-center gap-2">
        <div className={sect}>
          <Label className="text-xs text-muted-foreground">Operation</Label>
          <Select value={verb} onValueChange={(v) => setVerb(v as Verb)}>
            <SelectTrigger size="sm" className="h-8 w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {VERBS.map((v) => (
                <SelectItem key={v.value} value={v.value}>
                  {v.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className={sect}>
          <Label className="text-xs text-muted-foreground">Table</Label>
          <Select value={table} onValueChange={pickTable}>
            <SelectTrigger size="sm" className="h-8 w-48">
              <SelectValue placeholder="Select a table…" />
            </SelectTrigger>
            <SelectContent>
              {tables.map((t) => (
                <SelectItem key={t.name} value={t.name}>
                  {t.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="ml-auto flex items-end gap-2">
          <Button size="sm" onClick={generate} disabled={busy || !table}>
            <WandSparkles className="size-4" />
            {busy ? 'Generating…' : 'Generate & Run'}
          </Button>
        </div>
      </div>

      {(verb === 'select' || verb === 'count') && (
        <>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className={sect}>
              <Label className="text-xs text-muted-foreground">
                {verb === 'count' ? 'Distinct columns (optional)' : 'Columns (comma-separated)'}
              </Label>
              <Input value={columns} onChange={(e) => setColumns(e.target.value)} placeholder="id, name" className="h-8" />
            </div>
            <div className={sect}>
              <Label className="text-xs text-muted-foreground">Search term (LIKE)</Label>
              <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="ada" className="h-8" />
            </div>
          </div>
          <div className={sect}>
            <Label className="text-xs text-muted-foreground">
              Search in columns (comma-separated; required when searching)
            </Label>
            <Input value={searchColumns} onChange={(e) => setSearchColumns(e.target.value)} placeholder="name, email" className="h-8" />
          </div>
          <div className={sect}>
            <div className="flex items-center justify-between">
              <Label className="text-xs text-muted-foreground">Equality filters (AND)</Label>
              <Button variant="ghost" size="sm" className="h-6 text-xs" onClick={() => setEqRows((r) => [...r, { id: nextId(), col: '', value: '' }])}>
                <Plus className="size-3.5" /> Add
              </Button>
            </div>
            <div className={pairHeader}>
              {eqRows.map((r) => (
                <div key={r.id} className="col-span-3 grid grid-cols-[1fr_1fr_28px] gap-1.5">
                  <Input value={r.col} placeholder="column" className="h-7" onChange={(e) => updatePair(eqRows, setEqRows, r.id, { col: e.target.value })} />
                  <Input value={r.value} placeholder="value" className="h-7" onChange={(e) => updatePair(eqRows, setEqRows, r.id, { value: e.target.value })} />
                  <Button variant="ghost" size="icon" className="size-7" onClick={() => setEqRows((rs) => rs.filter((x) => x.id !== r.id))}>
                    <Trash2 className="size-3.5" />
                  </Button>
                </div>
              ))}
            </div>
          </div>
          <div className={sect}>
            <div className="flex items-center justify-between">
              <Label className="text-xs text-muted-foreground">Where clauses (AND)</Label>
              <Button variant="ghost" size="sm" className="h-6 text-xs" onClick={() => setWhereRows((r) => [...r, { id: nextId(), col: '', op: 'eq', value: '' }])}>
                <Plus className="size-3.5" /> Add
              </Button>
            </div>
            {whereRows.map((r) => (
              <div key={r.id} className="grid grid-cols-[1fr_110px_1fr_28px] items-center gap-1.5">
                <Input value={r.col} placeholder="column" className="h-7" onChange={(e) => updatePair(whereRows, setWhereRows, r.id, { col: e.target.value })} />
                <Select value={r.op} onValueChange={(op) => updatePair(whereRows, setWhereRows, r.id, { op })}>
                  <SelectTrigger size="sm" className="h-7">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {WHERE_OPS.map((op) => (
                      <SelectItem key={op} value={op}>
                        {op}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Input value={r.value} placeholder="value" className="h-7" onChange={(e) => updatePair(whereRows, setWhereRows, r.id, { value: e.target.value })} />
                <Button variant="ghost" size="icon" className="size-7" onClick={() => setWhereRows((rs) => rs.filter((x) => x.id !== r.id))}>
                  <Trash2 className="size-3.5" />
                </Button>
              </div>
            ))}
          </div>
          {verb === 'select' && (
            <>
              <label className="flex items-center gap-2">
                <input type="checkbox" className="size-3.5" checked={distinct} onChange={(e) => setDistinct(e.target.checked)} />
                <Label className="text-xs">DISTINCT</Label>
              </label>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className={sect}>
                  <Label className="text-xs text-muted-foreground">Order by (comma-separated)</Label>
                  <Input value={orderBy} onChange={(e) => setOrderBy(e.target.value)} placeholder="name, age" className="h-8" />
                </div>
                <div className={sect}>
                  <Label className="text-xs text-muted-foreground">Direction</Label>
                  <Select value={orderDir} onValueChange={setOrderDir}>
                    <SelectTrigger size="sm" className="h-8">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="asc">asc</SelectItem>
                      <SelectItem value="desc">desc</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="grid gap-3 sm:grid-cols-4">
                <div className={sect}>
                  <Label className="text-xs text-muted-foreground">Limit</Label>
                  <Input value={limit} onChange={(e) => setLimit(e.target.value)} placeholder="100" className="h-8" />
                </div>
                <div className={sect}>
                  <Label className="text-xs text-muted-foreground">Offset</Label>
                  <Input value={offset} onChange={(e) => setOffset(e.target.value)} placeholder="0" className="h-8" />
                </div>
                <div className={sect}>
                  <Label className="text-xs text-muted-foreground">Page (1-based)</Label>
                  <Input value={page} onChange={(e) => setPage(e.target.value)} placeholder="1" className="h-8" />
                </div>
                <div className={sect}>
                  <Label className="text-xs text-muted-foreground">Page size</Label>
                  <Input value={pageSize} onChange={(e) => setPageSize(e.target.value)} placeholder="20" className="h-8" />
                </div>
              </div>
            </>
          )}
        </>
      )}

      {(verb === 'insert' || verb === 'update' || verb === 'upsert') && (
        <div className={sect}>
          <div className="flex items-center justify-between">
            <Label className="text-xs text-muted-foreground">Values ({verb})</Label>
            <Button variant="ghost" size="sm" className="h-6 text-xs" onClick={() => setDataRows((r) => [...r, { id: nextId(), col: '', value: '' }])}>
              <Plus className="size-3.5" /> Add
            </Button>
          </div>
          {dataRows.map((r) => (
            <div key={r.id} className="grid grid-cols-[1fr_1fr_28px] items-center gap-1.5">
              <Input value={r.col} placeholder="column" className="h-7" onChange={(e) => updatePair(dataRows, setDataRows, r.id, { col: e.target.value })} />
              <Input value={r.value} placeholder="value" className="h-7" onChange={(e) => updatePair(dataRows, setDataRows, r.id, { value: e.target.value })} />
              <Button variant="ghost" size="icon" className="size-7" onClick={() => setDataRows((rs) => rs.filter((x) => x.id !== r.id))}>
                <Trash2 className="size-3.5" />
              </Button>
            </div>
          ))}
        </div>
      )}

      {(verb === 'update' || verb === 'delete') && (
        <div className={sect}>
          <div className="flex items-center justify-between">
            <Label className="text-xs text-muted-foreground">Primary key (target row)</Label>
            <Button variant="ghost" size="sm" className="h-6 text-xs" onClick={() => setPkRows((r) => [...r, { id: nextId(), col: '', value: '' }])}>
              <Plus className="size-3.5" /> Add
            </Button>
          </div>
          {pkRows.map((r) => (
            <div key={r.id} className="grid grid-cols-[1fr_1fr_28px] items-center gap-1.5">
              <Input value={r.col} placeholder="column" className="h-7" onChange={(e) => updatePair(pkRows, setPkRows, r.id, { col: e.target.value })} />
              <Input value={r.value} placeholder="value" className="h-7" onChange={(e) => updatePair(pkRows, setPkRows, r.id, { value: e.target.value })} />
              <Button variant="ghost" size="icon" className="size-7" onClick={() => setPkRows((rs) => rs.filter((x) => x.id !== r.id))}>
                <Trash2 className="size-3.5" />
              </Button>
            </div>
          ))}
        </div>
      )}

      {verb === 'upsert' && (
        <div className={sect}>
          <Label className="text-xs text-muted-foreground">Conflict columns (PK / unique, comma-separated)</Label>
          <Input value={conflictColumns} onChange={(e) => setConflictColumns(e.target.value)} placeholder="id" className="h-8" />
        </div>
      )}

      {busy && !table && (
        <p className="flex items-center gap-1.5 text-muted-foreground">
          <Loader2 className="size-3.5 animate-spin" /> Loading tables…
        </p>
      )}
    </div>
  )
}

function coerce(value: string): unknown {
  const t = value.trim()
  if (t === '') return null
  if (/^[+-]?\d+(\.\d+)?$/.test(t)) return Number(t)
  if (t === 'true') return true
  if (t === 'false') return false
  return t
}