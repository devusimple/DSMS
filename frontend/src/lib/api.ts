import type {
  ColumnDef,
  Connection,
  ConnectionCreate,
  GeneratedSql,
  RowAction,
  RowsOut,
  SqlRequest,
  SqlResult,
  TableCreate,
  TableInfo,
} from '@/lib/types'

const BASE = '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      if (body?.detail) {
        message = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
      }
    } catch {
      /* keep default message */
    }
    throw new Error(message)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export const api = {
  listConnections: () => request<Connection[]>('/connections'),

  createConnection: (body: ConnectionCreate) =>
    request<Connection>('/connections', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  deleteConnection: (id: string) =>
    request<void>(`/connections/${encodeURIComponent(id)}`, { method: 'DELETE' }),

  listTables: (connId: string) =>
    request<TableInfo[]>(`/connections/${connId}/tables`),

  createTable: (connId: string, body: TableCreate) =>
    request<TableInfo>(`/connections/${connId}/tables`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  dropTable: (connId: string, table: string) =>
    request<void>(`/connections/${connId}/tables/${encodeURIComponent(table)}`, {
      method: 'DELETE',
    }),

  tableSql: (connId: string, table: string) =>
    request<GeneratedSql>(
      `/connections/${connId}/tables/${encodeURIComponent(table)}/sql`
    ),

  addColumn: (connId: string, table: string, col: ColumnDef) =>
    request<{ ok: boolean }>(`/connections/${connId}/tables/${encodeURIComponent(table)}/columns`, {
      method: 'POST',
      body: JSON.stringify(col),
    }),

  dropColumn: (connId: string, table: string, column: string) =>
    request<{ ok: boolean }>(
      `/connections/${connId}/tables/${encodeURIComponent(table)}/columns/${encodeURIComponent(column)}`,
      { method: 'DELETE' }
    ),

  listRows: (connId: string, table: string) =>
    request<RowsOut>(`/connections/${connId}/tables/${encodeURIComponent(table)}/rows`),

  insertRow: (connId: string, table: string, action: RowAction) =>
    request<{ rowcount: number; statement: string }>(
      `/connections/${connId}/tables/${encodeURIComponent(table)}/rows`,
      { method: 'POST', body: JSON.stringify(action) }
    ),

  updateRow: (connId: string, table: string, action: RowAction) =>
    request<{ rowcount: number; statement: string }>(
      `/connections/${connId}/tables/${encodeURIComponent(table)}/rows`,
      { method: 'PUT', body: JSON.stringify(action) }
    ),

  deleteRow: (connId: string, table: string, action: RowAction) =>
    request<{ rowcount: number; statement: string }>(
      `/connections/${connId}/tables/${encodeURIComponent(table)}/rows`,
      { method: 'DELETE', body: JSON.stringify(action) }
    ),

  runSql: (connId: string, body: SqlRequest) =>
    request<SqlResult>(`/connections/${connId}/sql`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
}