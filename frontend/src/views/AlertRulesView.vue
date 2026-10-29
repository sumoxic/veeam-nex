<script setup lang="ts">
/**
 * 告警规则：控制哪些发现项会产生告警、通知哪些渠道。
 *
 * 数据来自 GET /alert-rules；渠道选项来自 GET /channels；目标选项来自 GET /targets。
 * 渠道路由（channel_routes）为「渠道 + 该渠道的级别门槛」列表。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createAlertRule,
  deleteAlertRule,
  listAlertRules,
  listChannels,
  listTargets,
  testAlertRule,
  updateAlertRule,
} from '@/api'
import type { AlertRule, ChannelRoute, NotificationChannel, Severity, Target } from '@/api/types'
import SeverityTag from '@/components/SeverityTag.vue'
import { formatDateTime, formatMinutes } from '@/utils/format'
import { asRow } from '@/utils/table'
import { useUserStore } from '@/stores/user'

const store = useUserStore()

/** 路由行；channel_id 为 0 表示尚未选择渠道 */
interface RouteRow {
  channel_id: number
  min_level: Severity
}

const LEVEL_OPTIONS: { label: string; value: Severity }[] = [
  { label: '严重', value: 'critical' },
  { label: '警告', value: 'warn' },
  { label: '提示', value: 'info' },
  { label: '正常', value: 'ok' },
]

const rules = ref<AlertRule[]>([])
const channels = ref<NotificationChannel[]>([])
const targets = ref<Target[]>([])
const loading = ref(false)

const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const saving = ref(false)

const form = reactive({
  name: '',
  enabled: true,
  match_rule_key: '',
  match_category: '',
  match_target_ids: [] as number[],
  min_level: 'warn' as Severity,
  cooldown_minutes: 60,
  dedup_window_hours: 24,
  notify_on_resolve: false,
  channel_routes: [] as RouteRow[],
})

function errorText(err: unknown, fallback: string): string {
  return err instanceof Error ? err.message : fallback
}

const targetNameMap = computed(() => {
  const map = new Map<number, string>()
  for (const t of targets.value) map.set(t.id, t.name)
  return map
})

/** 渠道下拉：已启用的渠道；当前规则引用了但已停用的渠道也保留，避免编辑时丢失路由 */
const channelOptions = computed(() => {
  const referenced = new Set(form.channel_routes.map((r) => r.channel_id))
  const enabled = channels.value.filter((c) => c.enabled)
  const extra = channels.value.filter((c) => !c.enabled && referenced.has(c.id))
  return [...enabled, ...extra]
})

const channelNameMap = computed(() => {
  const map = new Map<number, string>()
  for (const c of channels.value) map.set(c.id, c.name)
  return map
})

function channelName(id: number): string {
  return channelNameMap.value.get(id) ?? `渠道 #${id}`
}

/** 匹配目标的展示文本 */
function matchTargetText(rule: AlertRule): string {
  const ids = rule.match_target_ids
  if (!ids || !ids.length) return '全部目标'
  const names = ids.map((id) => targetNameMap.value.get(id) ?? `#${id}`)
  return names.join('、')
}

function routeText(rule: AlertRule): string {
  const routes = rule.channel_routes ?? []
  if (!routes.length) return '未配置'
  return routes
    .map((r) => `${channelName(r.channel_id)}(${levelLabel(r.min_level)})`)
    .join('、')
}

function levelLabel(level?: Severity | string | null): string {
  return LEVEL_OPTIONS.find((o) => o.value === level)?.label ?? (level ?? '-')
}

async function load() {
  loading.value = true
  try {
    const [ruleRes, channelRes, targetRes] = await Promise.all([
      listAlertRules(),
      listChannels(),
      listTargets(),
    ])
    rules.value = ruleRes.items ?? []
    channels.value = channelRes.items ?? []
    targets.value = targetRes.items ?? []
  } catch (err) {
    ElMessage.error(errorText(err, '加载告警规则失败'))
  } finally {
    loading.value = false
  }
}

function resetForm() {
  form.name = ''
  form.enabled = true
  form.match_rule_key = ''
  form.match_category = ''
  form.match_target_ids = []
  form.min_level = 'warn'
  form.cooldown_minutes = 60
  form.dedup_window_hours = 24
  form.notify_on_resolve = false
  form.channel_routes = []
}

function openCreate() {
  if (!store.canOperate) {
    ElMessage.warning('当前角色无权新建告警规则')
    return
  }
  resetForm()
  editingId.value = null
  dialogVisible.value = true
}

function openEdit(rule: AlertRule) {
  if (!store.canOperate) {
    ElMessage.warning('当前角色无权修改告警规则')
    return
  }
  resetForm()
  editingId.value = rule.id
  form.name = rule.name
  form.enabled = rule.enabled
  form.match_rule_key = rule.match_rule_key ?? ''
  form.match_category = rule.match_category ?? ''
  form.match_target_ids = [...(rule.match_target_ids ?? [])]
  form.min_level = rule.min_level
  form.cooldown_minutes = rule.cooldown_minutes
  form.dedup_window_hours = rule.dedup_window_hours
  form.notify_on_resolve = rule.notify_on_resolve
  form.channel_routes = (rule.channel_routes ?? []).map((r: ChannelRoute) => ({
    channel_id: r.channel_id,
    min_level: r.min_level,
  }))
  dialogVisible.value = true
}

function addRoute() {
  form.channel_routes.push({ channel_id: 0, min_level: form.min_level })
}

function removeRoute(index: number) {
  form.channel_routes.splice(index, 1)
}

function clearRoutes() {
  form.channel_routes = []
}

function buildPayload() {
  return {
    name: form.name.trim(),
    enabled: form.enabled,
    match_rule_key: form.match_rule_key.trim() || null,
    match_category: form.match_category.trim() || null,
    match_target_ids: form.match_target_ids.length ? [...form.match_target_ids] : null,
    min_level: form.min_level,
    cooldown_minutes: form.cooldown_minutes,
    dedup_window_hours: form.dedup_window_hours,
    notify_on_resolve: form.notify_on_resolve,
    channel_routes: form.channel_routes
      .filter((r) => r.channel_id > 0)
      .map((r) => ({ channel_id: r.channel_id, min_level: r.min_level })),
  }
}

async function onSave() {
  if (!store.canOperate) {
    ElMessage.warning('当前角色无权修改告警规则')
    return
  }
  if (!form.name.trim()) {
    ElMessage.warning('请填写规则名称')
    return
  }
  if (form.channel_routes.some((r) => r.channel_id <= 0)) {
    ElMessage.warning('存在未选择渠道的路由，请补全或删除')
    return
  }
  saving.value = true
  try {
    const payload = buildPayload()
    if (editingId.value === null) {
      await createAlertRule(payload)
      ElMessage.success('告警规则已创建')
    } else {
      await updateAlertRule(editingId.value, payload)
      ElMessage.success('告警规则已保存')
    }
    dialogVisible.value = false
    await load()
  } catch (err) {
    ElMessage.error(errorText(err, '保存告警规则失败'))
  } finally {
    saving.value = false
  }
}

/** 后端返回的字段随版本略有差异，这里统一转成可读文本 */
function describeTestResult(raw: unknown): { failed: number; text: string } {
  const info = (raw ?? {}) as Record<string, unknown>
  const parts: string[] = []
  if (typeof info.created === 'number') parts.push(`生成测试事件 ${info.created} 条`)
  if (typeof info.sent === 'number') parts.push(`发送成功 ${info.sent} 条`)
  if (typeof info.failed === 'number') parts.push(`发送失败 ${info.failed} 条`)
  if (typeof info.message === 'string' && info.message) parts.push(info.message)
  const failed = typeof info.failed === 'number' ? info.failed : 0
  return { failed, text: parts.length ? parts.join('，') : '测试完成' }
}

async function onTest(rule: AlertRule) {
  if (!store.canOperate) {
    ElMessage.warning('当前角色无权测试告警规则')
    return
  }
  try {
    const result = await testAlertRule(rule.id)
    const { failed, text } = describeTestResult(result)
    if (failed > 0) ElMessage.error(text)
    else ElMessage.success(text)
    await load()
  } catch (err) {
    ElMessage.error(errorText(err, '测试告警规则失败'))
  }
}

async function onDelete(rule: AlertRule) {
  if (!store.canOperate) {
    ElMessage.warning('当前角色无权删除告警规则')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确定删除告警规则「${rule.name}」吗？该规则下的告警事件也会一并清理。`,
      '删除告警规则',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await deleteAlertRule(rule.id)
    ElMessage.success('告警规则已删除')
    await load()
  } catch (err) {
    ElMessage.error(errorText(err, '删除告警规则失败'))
  }
}

onMounted(load)
</script>

<template>
  <div class="vi-page">
    <div class="vi-page-header">
      <h2 class="vi-page-title">告警规则</h2>
      <div class="vi-toolbar">
        <el-button @click="load">刷新</el-button>
        <el-button type="primary" :disabled="!store.canOperate" @click="openCreate">
          新建告警规则
        </el-button>
      </div>
    </div>

    <div class="vi-card">
      <el-table v-loading="loading" :data="rules" border stripe style="width: 100%">
        <el-table-column prop="name" label="名称" min-width="160" show-overflow-tooltip />
        <el-table-column label="启用" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'" size="small" effect="light">
              {{ row.enabled ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="匹配规则" min-width="140">
          <template #default="{ row }">
            <span v-if="row.match_rule_key" class="vi-mono">{{ row.match_rule_key }}</span>
            <span v-else class="vi-muted">全部规则</span>
          </template>
        </el-table-column>
        <el-table-column label="匹配类别" width="120">
          <template #default="{ row }">
            <span v-if="row.match_category">{{ row.match_category }}</span>
            <span v-else class="vi-muted">全部类别</span>
          </template>
        </el-table-column>
        <el-table-column label="匹配目标" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">{{ matchTargetText(asRow<AlertRule>(row)) }}</template>
        </el-table-column>
        <el-table-column label="最低级别" width="100" align="center">
          <template #default="{ row }">
            <SeverityTag :level="row.min_level" />
          </template>
        </el-table-column>
        <el-table-column label="渠道路由" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ routeText(asRow<AlertRule>(row)) }}</template>
        </el-table-column>
        <el-table-column label="冷却" width="110" align="center">
          <template #default="{ row }">{{ formatMinutes(row.cooldown_minutes) }}</template>
        </el-table-column>
        <el-table-column label="去重窗口" width="100" align="center">
          <template #default="{ row }">{{ row.dedup_window_hours }} 小时</template>
        </el-table-column>
        <el-table-column label="通知恢复" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.notify_on_resolve ? 'success' : 'info'" size="small" effect="light">
              {{ row.notify_on_resolve ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="更新时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="150" align="center" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" :disabled="!store.canOperate" @click="openEdit(asRow<AlertRule>(row))">
              编辑
            </el-button>
            <el-button link type="primary" :disabled="!store.canOperate" @click="onTest(asRow<AlertRule>(row))">
              测试
            </el-button>
            <el-button link type="danger" :disabled="!store.canOperate" @click="onDelete(asRow<AlertRule>(row))">
              删除
            </el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无告警规则" />
        </template>
      </el-table>
    </div>

    <el-dialog
      v-model="dialogVisible"
      :title="editingId === null ? '新建告警规则' : '编辑告警规则'"
      width="680px"
      top="6vh"
    >
      <el-form label-width="110px" :model="form">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="例如：严重告警邮件通知" maxlength="128" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.enabled" />
        </el-form-item>
        <el-form-item label="匹配规则">
          <el-input v-model="form.match_rule_key" placeholder="留空表示匹配全部规则" />
        </el-form-item>
        <el-form-item label="匹配类别">
          <el-input v-model="form.match_category" placeholder="留空表示匹配全部类别" />
        </el-form-item>
        <el-form-item label="匹配目标">
          <el-select
            v-model="form.match_target_ids"
            multiple
            collapse-tags
            collapse-tags-tooltip
            placeholder="留空表示匹配全部目标"
            style="width: 100%"
          >
            <el-option
              v-for="t in targets"
              :key="t.id"
              :label="t.name"
              :value="t.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="最低级别">
          <el-select v-model="form.min_level" style="width: 200px">
            <el-option
              v-for="opt in LEVEL_OPTIONS"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="冷却时间">
          <el-input-number
            v-model="form.cooldown_minutes"
            :min="0"
            :max="10080"
            :step="5"
            controls-position="right"
          />
          <span class="vi-muted unit-hint">分钟（同一指纹在该时间内不重复通知）</span>
        </el-form-item>
        <el-form-item label="去重窗口">
          <el-input-number
            v-model="form.dedup_window_hours"
            :min="1"
            :max="8760"
            :step="1"
            controls-position="right"
          />
          <span class="vi-muted unit-hint">小时</span>
        </el-form-item>
        <el-form-item label="通知恢复">
          <el-switch v-model="form.notify_on_resolve" />
          <span class="vi-muted unit-hint">发现项恢复时也发送一条通知</span>
        </el-form-item>

        <el-form-item label="渠道路由">
          <div class="route-editor">
            <div
              v-for="(route, index) in form.channel_routes"
              :key="index"
              class="route-row"
            >
              <el-select
                v-model="route.channel_id"
                placeholder="选择渠道"
                class="route-channel"
              >
                <el-option
                  v-for="c in channelOptions"
                  :key="c.id"
                  :label="c.enabled ? c.name : `${c.name}（已停用）`"
                  :value="c.id"
                />
              </el-select>
              <el-select v-model="route.min_level" class="route-level">
                <el-option
                  v-for="opt in LEVEL_OPTIONS"
                  :key="opt.value"
                  :label="opt.label"
                  :value="opt.value"
                />
              </el-select>
              <el-button link type="danger" @click="removeRoute(index)">删除</el-button>
            </div>
            <div class="route-actions">
              <el-button size="small" @click="addRoute">添加路由</el-button>
              <el-button
                size="small"
                type="danger"
                plain
                :disabled="form.channel_routes.length === 0"
                @click="clearRoutes"
              >
                清空路由
              </el-button>
            </div>
            <div v-if="channels.length === 0" class="vi-muted route-empty">
              还没有可用的通知渠道，请先到「通知渠道」页面创建。
            </div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.unit-hint {
  margin-left: 8px;
  font-size: 12px;
}

.route-editor {
  width: 100%;
}

.route-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.route-channel {
  width: 260px;
}

.route-level {
  width: 120px;
}

.route-actions {
  display: flex;
  gap: 8px;
}

.route-empty {
  font-size: 12px;
  margin-top: 6px;
}
</style>
