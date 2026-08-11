/** Convenience aliases onto the generated OpenAPI component schemas. */
import type { components } from './schema'

export type DatasetSummary = components['schemas']['DatasetSummary']
export type DatasetDetail = components['schemas']['DatasetDetail']
export type ColumnInfo = components['schemas']['ColumnInfo']
export type QualityIssue = components['schemas']['QualityIssueOut']
export type QualityReport = components['schemas']['QualityReportOut']
export type LineageEvent = components['schemas']['LineageEventOut']
export type Lineage = components['schemas']['LineageOut']
export type Preview = components['schemas']['PreviewOut']
export type KpiValue = components['schemas']['KpiValueOut']
export type KpiSummary = components['schemas']['KpiSummaryOut']
export type BreakdownItem = components['schemas']['BreakdownItemOut']
export type Breakdown = components['schemas']['BreakdownOut']
export type TrendPoint = components['schemas']['TrendPointOut']
export type Trend = components['schemas']['TrendOut']

// Auth / RBAC / audit (Phase 4)
export type CurrentUser = components['schemas']['UserOut']
export type TokenResponse = components['schemas']['TokenResponse']
export type UserAdmin = components['schemas']['UserAdminOut']
export type RoleInfo = components['schemas']['RoleOut']
export type PermissionInfo = components['schemas']['PermissionOut']
export type AuditLogEntry = components['schemas']['AuditLogOut']
export type AuditLogPage = components['schemas']['AuditLogPage']

/** The three fixed role names - kept as a literal union, not just `string`,
 * so the frontend can't reference a role the backend doesn't know about. */
export type RoleName = 'ADMIN' | 'ANALYST' | 'VIEWER'

/** Every permission the backend's catalog defines - see
 * backend/app/rbac/seed.py. Kept as a literal union for the same reason. */
export type PermissionName =
  | 'dataset:read'
  | 'dataset:create'
  | 'dataset:delete'
  | 'dashboard:read'
  | 'dashboard:configure'
  | 'user:read'
  | 'user:create'
  | 'user:update'
  | 'user:delete'
  | 'audit:read'
