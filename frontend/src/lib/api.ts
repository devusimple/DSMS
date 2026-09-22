import type {
  ColumnDef,
  Connection,
  ConnectionCreate,
  ForeignKeyCreate,
  GenerateSqlRequest,
  GeneratedSql,
  GeneratedSqlWithParams,
  IndexCreate,
  IndexInfo,
  RowAction,
  RowsOut,
  SqlRequest,
  SqlResult,
  TableCreate,
  TableInfo,
  TableRelationships,
} from "@/lib/types";

const BASE = "https://dsms-rouge.vercel.app/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) {
        message =
          typeof body.detail === "string"
            ? body.detail
            : JSON.stringify(body.detail);
      }
    } catch {
      /* keep default message */
    }
    throw new Error(message);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  listConnections: () => request<Connection[]>("/connections"),

  createConnection: (body: ConnectionCreate) =>
    request<Connection>("/connections", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  deleteConnection: (id: string) =>
    request<void>(`/connections/${encodeURIComponent(id)}`, {
      method: "DELETE",
    }),

  listTables: (connId: string) =>
    request<TableInfo[]>(`/connections/${connId}/tables`),

  createTable: (connId: string, body: TableCreate) =>
    request<TableInfo>(`/connections/${connId}/tables`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  dropTable: (connId: string, table: string) =>
    request<void>(
      `/connections/${connId}/tables/${encodeURIComponent(table)}`,
      {
        method: "DELETE",
      },
    ),

  tableSql: (connId: string, table: string) =>
    request<GeneratedSql>(
      `/connections/${connId}/tables/${encodeURIComponent(table)}/sql`,
    ),

  addColumn: (connId: string, table: string, col: ColumnDef) =>
    request<{ ok: boolean }>(
      `/connections/${connId}/tables/${encodeURIComponent(table)}/columns`,
      {
        method: "POST",
        body: JSON.stringify(col),
      },
    ),

  dropColumn: (connId: string, table: string, column: string) =>
    request<{ ok: boolean }>(
      `/connections/${connId}/tables/${encodeURIComponent(table)}/columns/${encodeURIComponent(column)}`,
      { method: "DELETE" },
    ),

  listRows: (connId: string, table: string) =>
    request<RowsOut>(
      `/connections/${connId}/tables/${encodeURIComponent(table)}/rows`,
    ),

  insertRow: (connId: string, table: string, action: RowAction) =>
    request<{ rowcount: number; statement: string }>(
      `/connections/${connId}/tables/${encodeURIComponent(table)}/rows`,
      { method: "POST", body: JSON.stringify(action) },
    ),

  updateRow: (connId: string, table: string, action: RowAction) =>
    request<{ rowcount: number; statement: string }>(
      `/connections/${connId}/tables/${encodeURIComponent(table)}/rows`,
      { method: "PUT", body: JSON.stringify(action) },
    ),

  deleteRow: (connId: string, table: string, action: RowAction) =>
    request<{ rowcount: number; statement: string }>(
      `/connections/${connId}/tables/${encodeURIComponent(table)}/rows`,
      { method: "DELETE", body: JSON.stringify(action) },
    ),

  listIndexes: (connId: string, table: string) =>
    request<IndexInfo[]>(
      `/connections/${connId}/tables/${encodeURIComponent(table)}/indexes`,
    ),

  createIndex: (connId: string, table: string, body: IndexCreate) =>
    request<{ ok: boolean }>(
      `/connections/${connId}/tables/${encodeURIComponent(table)}/indexes`,
      { method: "POST", body: JSON.stringify(body) },
    ),

  dropIndex: (connId: string, table: string, index: string) =>
    request<void>(
      `/connections/${connId}/tables/${encodeURIComponent(table)}/indexes/${encodeURIComponent(index)}`,
      { method: "DELETE" },
    ),

  listRelationships: (connId: string, table: string) =>
    request<TableRelationships>(
      `/connections/${connId}/tables/${encodeURIComponent(table)}/relationships`,
    ),

  createForeignKey: (connId: string, table: string, body: ForeignKeyCreate) =>
    request<{ ok: boolean }>(
      `/connections/${connId}/tables/${encodeURIComponent(table)}/foreign_keys`,
      { method: "POST", body: JSON.stringify(body) },
    ),

  dropForeignKey: (connId: string, table: string, name: string) =>
    request<void>(
      `/connections/${connId}/tables/${encodeURIComponent(table)}/foreign_keys/${encodeURIComponent(name)}`,
      { method: "DELETE" },
    ),

  listViews: (connId: string) =>
    request<string[]>(`/connections/${connId}/views`),

  viewRows: (connId: string, view: string) =>
    request<RowsOut>(
      `/connections/${connId}/views/${encodeURIComponent(view)}/rows`,
    ),

  runSql: (connId: string, body: SqlRequest) =>
    request<SqlResult>(`/connections/${connId}/sql`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  generateSql: (connId: string, body: GenerateSqlRequest) =>
    request<GeneratedSqlWithParams>(`/connections/${connId}/generate`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
