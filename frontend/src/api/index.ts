/**
 * 后端接口资源封装。
 *
 * 每个函数对应后端的一个路由，返回类型与 `api/types.ts` 中的接口定义保持一致。
 * 认证头、401 自动刷新、响应解包都在 `client.ts` 里完成，这里只负责拼 URL 和参数。
 */
import { del, get, post, put } from './client'
import type {
  AlertEvent,
  AlertRule,
  ChannelRoute,
  ConnectionTestResult,
  DashboardRunOption,
  DashboardSummary,
  Finding,
  FindingEvent,
  FindingsTrendPoint,
  ItemList,
  InspectionRun,
  InspectionRunDetail,
  NotificationChannel,
  OperationAudit,
  OperationKind,
  PageResult,
  RuleCatalogueItem,
  RuleConfigItem,
  RunDashboard,
  Severity,
  Target,
  TargetSchedule,
  TargetSummary,
  TrendPoint,
  User,
} from './types'

// ---------------------------------------------------------------- 认证

export interface LoginPayload {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in?: number
  user?: User
}

export function login(username: string, password: string) {
  return post<LoginPayload>('/auth/login', { username, password })
}

export function logout() {
  return post<null>('/auth/logout')
}

export function fetchMe() {
  return get<User>('/auth/me')
}

export function changePassword(oldPassword: string, newPassword: string) {
  return post<null>('/auth/password', { old_password: oldPassword, new_password: newPassword })
}

// ---------------------------------------------------------------- 目标

export function listTargets(params?: { enabled?: boolean; q?: string }) {
  return get<ItemList<Target>>('/targets', params as Record<string, unknown>)
}

export function getTarget(targetId: number) {
  return get<Target>(`/targets/${targetId}`)
}

export interface TargetIn {
  name: string
  host: string
  port?: number
  username: string
  password: string
  verify_tls?: boolean
  /** auto / 12 / 13 */
  version_preference?: string
  description?: string | null
  is_enabled?: boolean
  schedule_cron?: string | null
  schedule_timezone?: string
  schedule_enabled?: boolean
}

export function createTarget(payload: TargetIn) {
  return post<Target>('/targets', payload)
}

export function updateTarget(targetId: number, payload: Partial<TargetIn>) {
  return put<Target>(`/targets/${targetId}`, payload)
}

export function deleteTarget(targetId: number) {
  return del<null>(`/targets/${targetId}`)
}

export function testConnection(targetId: number) {
  return post<ConnectionTestResult>(`/targets/${targetId}/test-connection`)
}

export function getCapabilities(targetId: number) {
  return get<{ items: Record<string, string>; checked_at?: string | null }>(
    `/targets/${targetId}/capabilities`,
  )
}

export function getTargetSummary(targetId: number) {
  return get<TargetSummary>(`/targets/${targetId}/summary`)
}

export function getSchedule(targetId: number) {
  return get<TargetSchedule>(`/targets/${targetId}/schedule`)
}

export function updateSchedule(
  targetId: number,
  payload: { cron?: string | null; timezone?: string; enabled?: boolean },
) {
  return put<TargetSchedule>(`/targets/${targetId}/schedule`, payload)
}

// ---------------------------------------------------------------- 规则

export function listRuleCatalogue() {
  return get<PageResult<RuleCatalogueItem>>('/rules')
}

export function listRuleConfig() {
  return get<PageResult<RuleConfigItem>>('/rules/config')
}

export function updateRule(
  ruleKey: string,
  payload: { enabled?: boolean | null; level?: Severity | null; params?: Record<string, unknown> | null },
) {
  return put<RuleConfigItem>(`/rules/${ruleKey}`, payload)
}

export function resetRules() {
  return post<null>('/rules/reset')
}

export function listTargetRules(targetId: number) {
  return get<PageResult<RuleConfigItem>>(`/targets/${targetId}/rules`)
}

export function getTargetRule(targetId: number, ruleKey: string) {
  return get<RuleConfigItem>(`/targets/${targetId}/rules/${ruleKey}`)
}

export function setTargetRule(
  targetId: number,
  ruleKey: string,
  payload: { enabled?: boolean | null; level?: Severity | null; params?: Record<string, unknown> | null },
) {
  return put<RuleConfigItem>(`/targets/${targetId}/rules/${ruleKey}`, payload)
}

export function clearTargetRule(targetId: number, ruleKey: string) {
  return del<null>(`/targets/${targetId}/rules/${ruleKey}`)
}

// ---------------------------------------------------------------- 巡检

export function listInspections(params?: {
  target_id?: number
  status?: string
  page?: number
  size?: number
}) {
  return get<PageResult<InspectionRun>>('/inspections', params as Record<string, unknown>)
}

/** 后端建单后立即返回 run_id，采集在后台异步进行 */
export function triggerInspection(targetId: number) {
  return post<{ run_id: number; status: string; message?: string }>('/inspections', null, {
    params: { target_id: targetId },
  })
}

export function getInspection(runId: number) {
  return get<InspectionRunDetail>(`/inspections/${runId}`)
}

export function getRunFindings(runId: number) {
  return get<PageResult<Finding>>(`/inspections/${runId}/findings`)
}

export function getRunInventory(runId: number) {
  return get<{ inventory: Record<string, unknown> }>(`/inspections/${runId}/inventory`)
}

// ---------------------------------------------------------------- 发现

export function listFindings(params?: {
  target_id?: number
  level?: string
  category?: string
  status?: string
  rule_key?: string
  keyword?: string
  page?: number
  size?: number
}) {
  return get<PageResult<Finding>>('/findings', params as Record<string, unknown>)
}

export function getFinding(findingId: number) {
  return get<Finding>(`/findings/${findingId}`)
}

export function getFindingEvents(findingId: number) {
  return get<PageResult<FindingEvent>>(`/findings/${findingId}/events`)
}

export function acknowledgeFinding(findingId: number) {
  return post<Finding>(`/findings/${findingId}/ack`)
}

export function resolveFinding(findingId: number) {
  return post<Finding>(`/findings/${findingId}/resolve`)
}

export function bulkAcknowledge(payload: { finding_ids?: number[]; target_id?: number | null }) {
  return post<{ acknowledged: number }>('/findings/bulk-ack', payload)
}

export function findingsSummary(params?: { target_id?: number }) {
  return get<{ by_level: Record<string, number>; by_status: Record<string, number> }>(
    '/findings/summary',
    params as Record<string, unknown>,
  )
}

// ---------------------------------------------------------------- 告警规则

export interface AlertRuleIn {
  name: string
  enabled?: boolean
  match_rule_key?: string | null
  match_category?: string | null
  match_target_ids?: number[] | null
  min_level?: Severity
  channel_routes?: ChannelRoute[]
  cooldown_minutes?: number
  dedup_window_hours?: number
  notify_on_resolve?: boolean
}

export function listAlertRules() {
  return get<PageResult<AlertRule>>('/alert-rules')
}

export function getAlertRule(ruleId: number) {
  return get<AlertRule>(`/alert-rules/${ruleId}`)
}

export function createAlertRule(payload: AlertRuleIn) {
  return post<AlertRule>('/alert-rules', payload)
}

export function updateAlertRule(ruleId: number, payload: Partial<AlertRuleIn>) {
  return put<AlertRule>(`/alert-rules/${ruleId}`, payload)
}

export function deleteAlertRule(ruleId: number) {
  return del<null>(`/alert-rules/${ruleId}`)
}

export function testAlertRule(ruleId: number) {
  return post<{ ok: boolean; message?: string }>(`/alert-rules/${ruleId}/test`)
}

// ---------------------------------------------------------------- 通知渠道

export interface ChannelIn {
  name: string
  channel_type: 'smtp' | 'webhook'
  enabled?: boolean
  config?: Record<string, unknown>
  secret?: string | null
  headers?: Record<string, unknown> | null
}

export function listChannels(params?: { enabled?: boolean }) {
  return get<PageResult<NotificationChannel>>('/channels', params as Record<string, unknown>)
}

export function getChannel(channelId: number) {
  return get<NotificationChannel>(`/channels/${channelId}`)
}

export function createChannel(payload: ChannelIn) {
  return post<NotificationChannel>('/channels', payload)
}

export function updateChannel(channelId: number, payload: Partial<ChannelIn>) {
  return put<NotificationChannel>(`/channels/${channelId}`, payload)
}

export function deleteChannel(channelId: number) {
  return del<null>(`/channels/${channelId}`)
}

export function testChannel(channelId: number) {
  return post<{ ok: boolean; message?: string }>(`/channels/${channelId}/test`)
}

export function webhookTemplates() {
  return get<{ templates: string[]; sign_types: string[] }>('/channels/templates')
}

// ---------------------------------------------------------------- 告警事件

export function listAlertEvents(params?: {
  status?: string
  severity?: string
  target_id?: number
  alert_rule_id?: number
  page?: number
  size?: number
}) {
  return get<PageResult<AlertEvent>>('/alert-events', params as Record<string, unknown>)
}

export function getAlertEvent(eventId: number) {
  return get<AlertEvent>(`/alert-events/${eventId}`)
}

export function retryAlertEvent(eventId: number) {
  return post<AlertEvent>(`/alert-events/${eventId}/retry`)
}

// ---------------------------------------------------------------- 指标 / 仪表盘

export function dashboardSummary(params?: { target_id?: number }) {
  return get<DashboardSummary>('/dashboard/summary', params as Record<string, unknown>)
}

/** 近期巡检轮次，用于仪表盘按巡检时间切换 */
export function dashboardRuns(limit = 40) {
  return get<{ items: DashboardRunOption[]; total: number }>('/dashboard/runs', { limit })
}

/** 单轮巡检的完整快照仪表盘 */
export function dashboardRun(runId: number) {
  return get<RunDashboard>(`/dashboard/runs/${runId}`)
}

export function repositoryFreeSpaceTrend(params: {
  target_id: number
  repository_id?: string
  days?: number
}) {
  return get<{ items: TrendPoint[]; total: number }>(
    '/metrics/repository-free-space',
    params as Record<string, unknown>,
  )
}

export function jobLastRunTrend(params: { target_id: number; days?: number }) {
  return get<{ items: TrendPoint[]; total: number }>(
    '/metrics/job-last-run',
    params as Record<string, unknown>,
  )
}

export function restorePointAgeTrend(params: { target_id: number; days?: number }) {
  return get<{ items: TrendPoint[]; total: number }>(
    '/metrics/restore-point-age',
    params as Record<string, unknown>,
  )
}

export function findingsTrend(params?: { target_id?: number; days?: number }) {
  return get<{ items: FindingsTrendPoint[]; total: number }>(
    '/metrics/findings-trend',
    params as Record<string, unknown>,
  )
}

// ---------------------------------------------------------------- 远程操作

export function listOperationKinds() {
  return get<PageResult<OperationKind>>('/operations/kinds')
}

export function listOperations(params?: {
  target_id?: number
  status?: string
  kind?: string
  page?: number
  size?: number
}) {
  return get<PageResult<OperationAudit>>('/operations', params as Record<string, unknown>)
}

export function getOperation(requestId: string) {
  return get<OperationAudit>(`/operations/${requestId}`)
}

export function createOperation(payload: {
  target_id: number
  kind: string
  params?: Record<string, unknown>
}) {
  return post<OperationAudit>('/operations', payload)
}

export function confirmOperation(requestId: string, token: string) {
  return post<OperationAudit>(`/operations/${requestId}/confirm`, { token })
}

export function rejectOperation(requestId: string) {
  return post<OperationAudit>(`/operations/${requestId}/reject`)
}

// ---------------------------------------------------------------- 审计 / 用户

export function auditOperations(params?: {
  target_id?: number
  status?: string
  page?: number
  size?: number
}) {
  return get<PageResult<OperationAudit>>('/audit/operations', params as Record<string, unknown>)
}

export function listUsers() {
  return get<PageResult<User>>('/users')
}

export function createUser(payload: {
  username: string
  password: string
  email?: string | null
  display_name?: string | null
  role?: string
}) {
  return post<User>('/users', payload)
}

export function updateUser(
  userId: number,
  payload: {
    email?: string | null
    display_name?: string | null
    role?: string | null
    is_active?: boolean | null
  },
) {
  return put<User>(`/users/${userId}`, payload)
}

export function deleteUser(userId: number) {
  return del<null>(`/users/${userId}`)
}

export function resetUserPassword(userId: number, newPassword: string) {
  return post<User>(`/users/${userId}/reset-password`, { new_password: newPassword })
}

// ---------------------------------------------------------------- 系统

export function systemHealth() {
  return get<{
    status: string
    app: string
    version: string
    uptime_seconds: number
    database: { ok: boolean; error?: string | null; name?: string }
  }>('/system/health')
}
