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
  exclude_auto?: string[]
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

export interface GenerateSqlRequest {
  table: string
  verb: 'select' | 'count' | 'insert' | 'update' | 'delete' | 'upsert'
  columns?: string[]
  eq?: Record<string, unknown>
  where?: [string, string, unknown][]
  search?: string
  search_columns?: string[]
  distinct?: boolean
  order_by?: string | string[]
  order_dir?: string
  limit?: number
  offset?: number
  page?: number
  page_size?: number
  data?: Record<string, unknown>
  pk?: Record<string, unknown>
  conflict_columns?: string[]
}

export interface GeneratedSqlWithParams {
  sql: string
  params: Record<string, unknown>
}

export interface IndexInfo {
  name: string
  columns: string[]
  unique: boolean
}

export interface IndexCreate {
  name: string
  columns: string[]
  unique: boolean
}

export type Cardinality = '1:1' | '1:N' | 'N:1'

export interface ForeignKeyInfo {
  name: string
  columns: string[]
  referred_table: string
  referred_columns: string[]
  on_delete: string
  on_update: string
  cardinality: Cardinality
}

export interface ReferencingForeignKeyInfo {
  table: string
  name: string
  columns: string[]
  referred_columns: string[]
  on_delete: string
  on_update: string
  cardinality: Cardinality
}

export interface ManyToManyInfo {
  endpoint: string
  through: string
}

export interface TableRelationships {
  junction: boolean
  outbound: ForeignKeyInfo[]
  inbound: ReferencingForeignKeyInfo[]
  many_to_many: ManyToManyInfo[]
}

export interface ForeignKeyCreate {
  name?: string
  columns: string[]
  referred_table: string
  referred_columns: string[]
  on_delete?: string
  on_update?: string
}

export const FK_ACTIONS = ['', 'NO ACTION', 'RESTRICT', 'CASCADE', 'SET NULL', 'SET DEFAULT'] as const