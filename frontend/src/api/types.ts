/** 后端数据模型的前端类型定义（与 openapi.json 保持一致）。 */

export type Severity = 'critical' | 'warn' | 'info' | 'ok'
export type FindingStatus = 'open' | 'acknowledged' | 'resolved'
export type RunStatus = 'running' | 'success' | 'failed' | 'partial'
export type UserRole = 'admin' | 'operator' | 'viewer'
export type OperationStatus =
  | 'pending'
  | 'executing'
  | 'succeeded'
  | 'failed'
  | 'expired'
  | 'rejected'
export type AlertEventStatus = 'pending' | 'sent' | 'failed' | 'suppressed'

export interface PageResult<T> {
  items: T[]
  total: number
  page?: number
  size?: number
}

/** 不分页的列表接口（targets / users） */
export interface ItemList<T> {
  items: T[]
}

export interface User {
  id: number
  username: string
  email?: string | null
  display_name?: string | null
  role: UserRole
  is_active: boolean
  last_login_at?: string | null
  created_at: string
}

export interface Target {
  id: number
  name: string
  host: string
  port: number
  username: string
  verify_tls: boolean
  /** auto / 12 / 13 */
  version_preference: string
  /** 实际使用的 REST API 版本，例如 1.2-rev1 */
  api_version?: string | null
  /** 探测到的 VBR 构建号，例如 12.3.2.3617 */
  detected_version?: string | null
  description?: string | null
  is_enabled: boolean
  schedule_cron?: string | null
  schedule_timezone: string
  schedule_enabled: boolean
  capabilities_checked_at?: string | null
  last_run_at?: string | null
  last_run_status?: string | null
  has_password: boolean
  created_at: string
  updated_at: string
}

export interface TargetSchedule {
  cron: string | null
  timezone: string
  enabled: boolean
}

export interface ConnectionTestResult {
  ok: boolean
  server: Record<string, unknown>
  server_time?: string | null
  iana_tz?: string | null
  /** VBR 构建号 */
  version?: string | null
  /** REST API 版本 */
  api_version?: string | null
  error?: string | null
}

export interface CapabilityItem {
  path: string
  /** ok / license-restricted / not-found / unauthorized / error: ... */
  status: string
  available: boolean
  error?: string | null
}

export interface InspectionRun {
  id: number
  target_id: number
  trigger_type: string
  status: RunStatus
  started_at: string
  finished_at?: string | null
  duration_ms?: number | null
  clock_source: string
  vbr_server_time?: string | null
  vbr_build?: string | null
  findings_total: number
  findings_critical: number
  findings_warn: number
  findings_info: number
  error_count: number
  error_message?: string | null
  created_at: string
}

export interface InspectionRunDetail extends InspectionRun {
  inventory_json?: Record<string, unknown> | null
}

export interface Finding {
  id: number
  target_id: number
  fingerprint: string
  rule_key: string
  category: string
  level: Severity
  subject: string
  subject_key: string
  message: string
  metric_value?: number | null
  threshold_value?: number | null
  status: FindingStatus
  occurrences: number
  first_seen_at: string
  last_seen_at: string
  last_run_id?: number | null
  resolved_at?: string | null
  acknowledged_by?: number | null
  acknowledged_at?: string | null
}

export interface FindingEvent {
  id: number
  finding_id: number
  run_id: number
  fingerprint: string
  level: Severity
  message?: string | null
  created_at: string
}

export interface RuleParamSchema {
  key: string
  label: string
  type: 'string' | 'number' | 'boolean'
  default: unknown
  min?: number
  max?: number
  placeholder?: string
}

export interface RuleCatalogueItem {
  rule_key: string
  category: string
  title: string
  description: string
  default_level: Severity
  collection?: string | null
  default_params: Record<string, unknown>
  param_schema: RuleParamSchema[]
}

export interface RuleConfigItem {
  rule_key: string
  enabled: boolean
  level?: Severity | null
  params: Record<string, unknown>
}

export interface ChannelRoute {
  channel_id: number
  min_level: Severity
}

export interface AlertRule {
  id: number
  name: string
  enabled: boolean
  match_rule_key?: string | null
  match_category?: string | null
  match_target_ids?: number[] | null
  min_level: Severity
  channel_routes: ChannelRoute[]
  cooldown_minutes: number
  dedup_window_hours: number
  notify_on_resolve: boolean
  created_by?: number | null
  updated_by?: number | null
  created_at: string
  updated_at: string
}

export interface NotificationChannel {
  id: number
  name: string
  channel_type: 'smtp' | 'webhook'
  enabled: boolean
  config: Record<string, unknown>
  headers: Record<string, unknown>
  has_secret: boolean
  last_test_at?: string | null
  last_test_status?: string | null
  created_at: string
  updated_at: string
}

export interface AlertEvent {
  id: number
  alert_rule_id: number
  channel_id: number
  target_id?: number | null
  finding_id?: number | null
  run_id?: number | null
  fingerprint: string
  dedup_key: string
  event_type: 'raised' | 'resolved' | 'escalated'
  severity: Severity
  title?: string | null
  body?: string | null
  status: AlertEventStatus
  attempts: number
  error_message?: string | null
  sent_at?: string | null
  created_at: string
}

export interface OperationAudit {
  id: number
  request_id: string
  target_id: number
  operator_id?: number | null
  operation_kind: string
  params: Record<string, unknown>
  preview_text: string
  status: OperationStatus
  token_expires_at: string
  confirmed_at?: string | null
  vbr_task_id?: string | null
  result?: Record<string, unknown> | null
  error_message?: string | null
  created_at: string
  updated_at: string
}

export interface OperationKind {
  kind: string
  description: string
  id_param: string
}

export interface TargetSummary {
  target: Target
  last_run: {
    id: number
    status: RunStatus
    started_at: string
    finished_at?: string | null
    findings_critical: number
    findings_warn: number
  } | null
  open_findings: Record<Severity, number>
}

export interface LicenseSummary {
  status?: string | null
  edition?: string | null
  licensed_to?: string | null
  used_instances?: number | null
  licensed_instances?: number | null
  used_percent?: number | null
  expiration_date?: string | null
}

export interface DashboardTargetCard {
  target: {
    id: number
    name: string
    host: string
    is_enabled: boolean
    last_run_at?: string | null
    last_run_status?: string | null
  }
  last_run: {
    id: number
    status: RunStatus
    started_at: string
    duration_ms?: number | null
    findings_critical: number
    findings_warn: number
  } | null
  open_findings: Record<Severity, number>
  license: LicenseSummary
}

export interface DashboardSummary {
  targets: DashboardTargetCard[]
  findings_by_level: Record<string, number>
  findings_by_status: Record<string, number>
  runs_by_status: Record<string, number>
  total_targets: number
}

export interface TrendPoint {
  time: string
  value: number | null
}

export interface FindingsTrendPoint {
  time: string
  critical: number
  warn: number
  info: number
}

export interface TrendSeries {
  points: TrendPoint[]
  [key: string]: unknown
}

// ---------------------------------------------------------------- 按轮次仪表盘

export interface DashboardRunOption {
  id: number
  target_id: number
  target_name: string
  status: RunStatus
  trigger_type: string
  started_at: string
  finished_at?: string | null
  duration_ms?: number | null
  vbr_build?: string | null
  findings_total: number
  findings_critical: number
  findings_warn: number
  findings_info: number
  error_count: number
}

export interface RunDashboardJob {
  id?: string | null
  name?: string | null
  type?: string | null
  workload?: string | null
  status?: string | null
  last_result?: string | null
  last_run_at?: string | null
  next_run?: string | null
  next_run_policy?: string | null
  repository_name?: string | null
  objects_count?: number | null
  progress_percent?: number | null
  session_duration?: string | null
  bottleneck?: string | null
  is_disabled?: boolean
}

export interface RunDashboardRepository {
  id?: string | null
  name?: string | null
  path?: string | null
  type?: string | null
  host_name?: string | null
  capacity_gb?: number | null
  free_gb?: number | null
  used_space_gb?: number | null
  free_percent?: number | null
  is_online?: boolean | null
  is_out_of_date?: boolean | null
}

export interface RunDashboardRestorePoint {
  id?: string | null
  name?: string | null
  type?: string | null
  creation_time?: string | null
  age_hours?: number | null
  malware_status?: string | null
  original_size?: number | null
}

export interface RunDashboardBackupObject {
  id?: string | null
  name?: string | null
  path?: string | null
  size?: number | null
  type?: string | null
  last_run_failed?: boolean | null
  restore_points_count?: number | null
}

export interface RunDashboardProxy {
  id?: string | null
  name?: string | null
  type?: string | null
  host_name?: string | null
  is_online?: boolean | null
  is_disabled?: boolean | null
  is_out_of_date?: boolean | null
}

export interface RunDashboardServer {
  id?: string | null
  name?: string | null
  type?: string | null
  status?: string | null
  vi_host_type?: string | null
  is_backup_server?: boolean | null
  description?: string | null
}

export interface RunDashboardService {
  name?: string | null
  port?: number | null
}

export interface RunDashboardSession {
  id?: string | null
  name?: string | null
  session_type?: string | null
  state?: string | null
  result?: string | null
  message?: string | null
  creation_time?: string | null
  end_time?: string | null
  progress_percent?: number | null
  initiated_by?: string | null
}

export interface RunDashboardFinding {
  id: number
  level: Severity
  rule_key: string
  category: string
  subject: string
  message: string
  status: FindingStatus
  last_seen_at: string
}

export interface RunDashboard {
  run: {
    id: number
    target_id: number
    status: RunStatus
    trigger_type: string
    started_at: string
    finished_at?: string | null
    duration_ms?: number | null
    clock_source: string
    vbr_server_time?: string | null
    vbr_build?: string | null
    findings_total: number
    findings_critical: number
    findings_warn: number
    findings_info: number
    error_count: number
    error_message?: string | null
  }
  target: { id: number; name: string; host: string; is_enabled: boolean }
  server: {
    name?: string | null
    build_version?: string | null
    platform?: string | null
    database_vendor?: string | null
    database_version?: string | null
    database_schema_version?: string | null
  }
  license: LicenseSummary & {
    type?: string | null
    support_id?: string | null
    package?: string | null
  }
  jobs: RunDashboardJob[]
  job_stats: {
    total: number
    success: number
    warning: number
    failed: number
    running: number
    disabled: number
    unknown: number
  }
  repositories: RunDashboardRepository[]
  repo_stats: {
    total: number
    online: number
    capacity_gb: number
    free_gb: number
    used_gb: number
    free_percent?: number | null
  }
  restore_points: {
    total: number
    avg_age_hours?: number | null
    max_age_hours?: number | null
    clean: number
    warning: number
    unknown: number
    items: RunDashboardRestorePoint[]
  }
  backup_objects: {
    total: number
    total_size: number
    failed: number
    items: RunDashboardBackupObject[]
  }
  proxies: RunDashboardProxy[]
  managed_servers: RunDashboardServer[]
  services: RunDashboardService[]
  sessions: RunDashboardSession[]
  findings: RunDashboardFinding[]
  findings_by_level: Record<'critical' | 'warn' | 'info', number>
}
