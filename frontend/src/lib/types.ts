export type Dialect = 'sqlite' | 'postgresql' | 'mysql'

export interface Connection {
  id: string
  name: string
  dialect: Dialect
  url: string
}

export interface ConnectionCreate {
  name: string
  dialect: Dialect
  dsn?: string
  host?: string
  port?: number
  database?: string
  username?: string
  password?: string
  file?: string
}

export interface ColumnInfo {
  name: string
  data_type: string
  primary_key: boolean
  nullable: boolean
  unique: boolean
  default: string | null
}

export interface TableInfo {
  name: string
  columns: ColumnInfo[]
}

export interface ColumnDef {
  name: string
  data_type: string
  primary_key?: boolean
  nullable?: boolean
  unique?: boolean
  default?: string | null
}

export interface TableCreate {
  name: string
  columns: ColumnDef[]
}

export interface RowAction {
  data: Record<string, unknown>
  pk?: Record<string, unknown>
}

export interface RowsOut {
  columns: string[]
  rows: Record<string, unknown>[]
}

export interface SqlRequest {
  statement: string
  params?: Record<string, unknown> | unknown[] | null
}

export interface SqlResult {
  columns: string[]
  rows: unknown[][]
  rowcount: number
}

export interface GeneratedSql {
  sql: string
}