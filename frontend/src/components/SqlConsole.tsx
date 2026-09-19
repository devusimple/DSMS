import { useCallback, useEffect, useRef, useState } from 'react'
import { History, Play, Trash2, WandSparkles } from 'lucide-react'

import { api } from '@/lib/api'
import type { Connection, SqlResult } from '@/lib/types'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import { QueryBuilder } from '@/components/QueryBuilder'

const HISTORY_KEY = (connId: string) => `dsms:sql-history:${connId}`

function loadHistory(connId: string): string[] {
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY(connId)) ?? '[]')
  } catch {
    return []
  }
}

function stringifyCell(value: unknown): string {
  if (value === null || value === undefined) return 'NULL'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

export function SqlConsole({ connection }: { connection: Connection }) {
  const [statement, setStatement] = useState('')
  const [paramsText, setParamsText] = useState('{}')
  const [result, setResult] = useState<SqlResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const [history, setHistory] = useState<string[]>(() => loadHistory(connection.id))
  const [showParams, setShowParams] = useState(false)
  const [builderOpen, setBuilderOpen] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    setHistory(loadHistory(connection.id))
    setStatement('')
    setResult(null)
    setError(null)
  }, [connection.id])

  const persist = useCallback(
    (entry: string) => {
      const next = [entry, ...history.filter((h) => h !== entry)].slice(0, 20)
      setHistory(next)
      localStorage.setItem(HISTORY_KEY(connection.id), JSON.stringify(next))
    },
    [history, connection.id]
  )

  const execute = useCallback(
    async (sql: string, params: Record<string, unknown> | unknown[] | null) => {
      const trimmed = sql.trim()
      if (!trimmed) return
      setRunning(true)
      setError(null)
      setResult(null)
      try {
        const res = await api.runSql(connection.id, { statement: trimmed, params })
        setResult(res)
        persist(trimmed)
      } catch (err) {
        setError((err as Error).message)
      } finally {
        setRunning(false)
      }
    },
    [connection.id, persist]
  )

  const run = async (textOverride?: string) => {
    const sql = (textOverride ?? statement).trim()
    if (!sql) return
    try {
      let params: Record<string, unknown> | unknown[] | null = null
      if (showParams && paramsText.trim()) {
        params = JSON.parse(paramsText)
      }
      await execute(sql, params)
    } catch (err) {
      setError((err as Error).message)
    }
  }

  const runFromBuilder = (sql: string, params: Record<string, unknown> | null) => {
    const paramsTextValue = params ? JSON.stringify(params, null, 2) : ''
    setStatement(sql)
    setParamsText(paramsTextValue)
    setShowParams(!!params)
    void execute(sql, params)
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault()
        run()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [statement, showParams, paramsText, run])

  const clearHistory = () => {
    setHistory([])
    localStorage.removeItem(HISTORY_KEY(connection.id))
  }

  const exportCsv = () => {
    if (!result || result.columns.length === 0) return
    const rows = result.rows.map((r) => r.map((c) => `"${String(c ?? '').replaceAll('"', '""')}"`).join(','))
    const csv = [result.columns.join(','), ...rows].join('\n')
    download(`${connection.name}-query.csv`, csv, 'text/csv')
  }

  const exportJson = () => {
    if (!result) return
    const obj = result.rows.map((r) =>
      Object.fromEntries(result.columns.map((c, i) => [c, r[i]]))
    )
    download(`${connection.name}-query.json`, JSON.stringify(obj, null, 2), 'application/json')
  }

  return (
    <div className="flex h-full min-w-0 flex-1 flex-col gap-3">
      <div className="grid min-h-24 flex-none gap-1.5">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-muted-foreground">
            SQL statement — press Ctrl+Enter to run
          </span>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              className="h-6 text-xs text-muted-foreground"
              onClick={() => setBuilderOpen((v) => !v)}
            >
              <WandSparkles className="size-3.5" />
              Builder
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-6 text-xs text-muted-foreground"
              onClick={() => setShowParams((v) => !v)}
            >
              Params {showParams ? 'hide' : 'show'}
            </Button>
          </div>
        </div>
        {builderOpen && (
          <QueryBuilder connection={connection} onGenerated={runFromBuilder} />
        )}
        <Textarea
          ref={textareaRef}
          value={statement}
          onChange={(e) => setStatement(e.target.value)}
          placeholder="SELECT * FROM users;"
          className="min-h-24 resize-y font-mono text-xs"
          spellCheck={false}
        />
        {showParams && (
          <Textarea
            value={paramsText}
            onChange={(e) => setParamsText(e.target.value)}
            placeholder='{"id": 1} or [1, "Ada"]'
            className="min-h-12 resize-y font-mono text-xs"
            spellCheck={false}
          />
        )}
        <div className="flex items-center gap-2">
          <Button size="sm" onClick={() => run()} disabled={running || !statement.trim()}>
            <Play className="size-4" />
            {running ? 'Running…' : 'Run'}
          </Button>
          <div className="flex gap-1 text-xs text-muted-foreground">
            <span>·</span>
            <span>Ctrl+Enter</span>
          </div>
        </div>
      </div>

      {error && (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 font-mono text-xs text-destructive">
          {error}
        </div>
      )}

      {result && (
        <div className="flex min-h-0 flex-1 flex-col gap-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">
              {result.columns.length > 0
                ? `${result.rows.length} row(s) · ${result.columns.length} column(s)`
                : `${result.rowcount} row(s) affected`}
            </span>
            {result.columns.length > 0 && (
              <div className="flex gap-1.5">
                <Button variant="outline" size="sm" className="h-6 text-xs" onClick={exportCsv}>
                  Export CSV
                </Button>
                <Button variant="outline" size="sm" className="h-6 text-xs" onClick={exportJson}>
                  Export JSON
                </Button>
              </div>
            )}
          </div>
          {result.columns.length > 0 && (
            <div className="min-h-0 flex-1 overflow-auto rounded-md border">
              <Table className="text-xs">
                <TableHeader>
                  <TableRow>
                    {result.columns.map((c) => (
                      <TableHead key={c} className="bg-muted/40">
                        {c}
                      </TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {result.rows.map((row, i) => (
                    <TableRow key={i}>
                      {row.map((cell, j) => (
                        <TableCell key={j} className="font-mono text-xs">
                          {stringifyCell(cell)}
                        </TableCell>
                      ))}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </div>
      )}

      {history.length > 0 && (
        <div className="flex-none border-t pt-2">
          <div className="mb-1.5 flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
              <History className="size-3.5" /> History
            </span>
            <Button variant="ghost" size="sm" className="h-6 text-xs text-muted-foreground" onClick={clearHistory}>
              <Trash2 className="size-3.5" /> Clear
            </Button>
          </div>
          <div className="flex max-h-28 flex-col gap-1 overflow-y-auto">
            {history.map((sql, i) => (
              <button
                key={i}
                className="truncate rounded px-2 py-1 text-left font-mono text-xs text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                title={sql}
                onClick={() => {
                  setStatement(sql)
                  setResult(null)
                  setError(null)
                }}
              >
                {sql}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function download(filename: string, content: string, type: string) {
  const blob = new Blob([content], { type })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
  void a
}