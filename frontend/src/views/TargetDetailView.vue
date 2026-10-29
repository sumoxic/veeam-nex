/**
 * 巡检目标详情页：概览 / 排期 / 规则覆盖 / 运行历史。
 *
 * 说明：
 *  - 能力探测接口返回的 `items` 在后端是 `{path: 状态}` 字典（历史版本是对象数组），
 *    这里统一归一化成 CapabilityItem 再渲染；
 *  - 后端没有「列出某目标规则覆盖」的接口，只有单条查询（未覆盖时 404），
 *    因此逐条探测来判断某条规则是否处于「继承全局」状态。
 */
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import JsonViewer from '@/components/JsonViewer.vue'
import StatusTag from '@/components/StatusTag.vue'
import {
  clearTargetRule,
  getCapabilities,
  getSchedule,
  getTarget,
  getTargetRule,
  listInspections,
  listRuleCatalogue,
  listTargetRules,
  setTargetRule,
  testConnection,
  updateSchedule,
} from '@/api'
import type {
  CapabilityItem,
  ConnectionTestResult,
  InspectionRun,
  RuleConfigItem,
  RuleParamSchema,
  Severity,
  Target,
} from '@/api/types'
import { useUserStore } from '@/stores/user'
import { formatDateTime, formatDuration } from '@/utils/format'
import { asRow } from '@/utils/table'

type LevelOption = Severity | 'inherit'

interface RuleRow {
  ruleKey: string
  title: string
  category: string
  description: string
  defaultLevel: Severity
  schema: RuleParamSchema[]
  /** null 表示继承全局 */
  enabled: boolean | null
  level: LevelOption
  params: Record<string, any>
  initialEnabled: boolean | null
  initialLevel: LevelOption
  initialParams: Record<string, any>
  /** 生效值（未覆盖时即全局值），用于继承状态下展示开关状态 */
  effectiveEnabled: boolean
}

const route = useRoute()
const router = useRouter()
const store = useUserStore()

const targetId = computed(() => Number(route.params.id))

function errMsg(err: unknown): string {
  return err instanceof Error ? err.message : '操作失败'
}

// ------------------------------------------------------------------ 概览

const target = ref<Target | null>(null)
const overviewLoading = ref(false)

async function loadTarget() {
  overviewLoading.value = true
  try {
    target.value = await getTarget(targetId.value)
  } catch (err) {
    ElMessage.error(errMsg(err))
  } finally {
    overviewLoading.value = false
  }
}

// ------------------------------------------------------------------ 能力探测

const capabilities = ref<CapabilityItem[]>([])
const capsCheckedAt = ref<string | null>(null)
const capsLoading = ref(false)

function normalizeCapabilities(raw: unknown): CapabilityItem[] {
  if (Array.isArray(raw)) return raw as CapabilityItem[]
  if (raw && typeof raw === 'object') {
    return Object.entries(raw as Record<string, unknown>).map(([path, value]) => {
      const text = String(value ?? '')
      return {
        path,
        status: text,
        available: text === 'ok',
        error: text === 'ok' ? null : text,
      }
    })
  }
  return []
}

async function loadCapabilities() {
  capsLoading.value = true
  try {
    const res = await getCapabilities(targetId.value)
    // 声明类型是 CapabilityItem[]，后端实际返回 {path: 状态} 字典，这里统一归一化
    capabilities.value = normalizeCapabilities(res.items)
    capsCheckedAt.value = res.checked_at ?? null
  } catch (err) {
    ElMessage.error(errMsg(err))
  } finally {
    capsLoading.value = false
  }
}

// ------------------------------------------------------------------ 连通性测试

const testVisible = ref(false)
const testing = ref(false)
const testResult = ref<ConnectionTestResult | null>(null)

async function testConnectionNow() {
  testing.value = true
  testResult.value = null
  try {
    testResult.value = await testConnection(targetId.value)
    testVisible.value = true
  } catch (err) {
    ElMessage.error(errMsg(err))
  } finally {
    testing.value = false
  }
}

// ------------------------------------------------------------------ 排期

const scheduleCron = ref('')
const scheduleTimezone = ref('Asia/Shanghai')
const scheduleEnabled = ref(false)
const scheduleSaving = ref(false)

async function loadSchedule() {
  try {
    const res = await getSchedule(targetId.value)
    scheduleCron.value = res.cron ?? ''
    scheduleTimezone.value = res.timezone || 'Asia/Shanghai'
    scheduleEnabled.value = res.enabled
  } catch (err) {
    ElMessage.error(errMsg(err))
  }
}

async function saveSchedule() {
  scheduleSaving.value = true
  try {
    await updateSchedule(targetId.value, {
      cron: scheduleCron.value.trim() || null,
      timezone: scheduleTimezone.value.trim() || 'Asia/Shanghai',
      enabled: scheduleEnabled.value,
    })
    ElMessage.success('排期已保存')
    await loadSchedule()
    await loadTarget()
  } catch (err) {
    ElMessage.error(errMsg(err))
  } finally {
    scheduleSaving.value = false
  }
}

// ------------------------------------------------------------------ 规则覆盖

const rulesLoading = ref(false)
const ruleRows = ref<RuleRow[]>([])
const batchSaving = ref(false)

const LEVEL_OPTIONS: { value: LevelOption; label: string }[] = [
  { value: 'inherit', label: '继承' },
  { value: 'critical', label: '严重' },
  { value: 'warn', label: '警告' },
  { value: 'info', label: '提示' },
  { value: 'ok', label: '正常' },
]

const LEVEL_LABELS: Record<string, string> = {
  critical: '严重',
  warn: '警告',
  info: '提示',
  ok: '正常',
}

const CATEGORY_LABELS: Record<string, string> = {
  server: '服务器',
  license: '许可',
  job: '作业',
  'restore-point': '还原点',
  repository: '仓库',
  proxy: '代理',
  'managed-server': '受管服务器',
  'backup-object': '受保护对象',
}

function categoryLabel(key: string): string {
  return CATEGORY_LABELS[key] ?? key
}

async function probeOverride(ruleKey: string): Promise<{ exists: boolean; data?: RuleConfigItem }> {
  try {
    const data = await getTargetRule(targetId.value, ruleKey)
    return { exists: true, data }
  } catch {
    return { exists: false }
  }
}

async function loadRules() {
  rulesLoading.value = true
  try {
    const [catalogueRes, effectiveRes] = await Promise.all([
      listRuleCatalogue(),
      listTargetRules(targetId.value),
    ])
    const catalogue = catalogueRes.items ?? []
    const effective = new Map(
      (effectiveRes.items ?? []).map((item) => [item.rule_key, item] as const),
    )
    const overrides = await Promise.all(catalogue.map((item) => probeOverride(item.rule_key)))

    ruleRows.value = catalogue.map((item, index) => {
      const eff = effective.get(item.rule_key)
      const override = overrides[index]
      const overrideData = override.data
      const schema = item.param_schema ?? []
      const params: Record<string, any> = {}
      for (const spec of schema) {
        const value = eff?.params?.[spec.key] ?? item.default_params?.[spec.key] ?? spec.default
        params[spec.key] = value
      }
      const enabled: boolean | null = override.exists ? (overrideData?.enabled ?? null) : null
      const level: LevelOption = overrideData?.level ? overrideData.level : 'inherit'
      return {
        ruleKey: item.rule_key,
        title: item.title,
        category: item.category,
        description: item.description,
        defaultLevel: item.default_level,
        schema,
        enabled,
        level,
        params: { ...params },
        initialEnabled: enabled,
        initialLevel: level,
        initialParams: { ...params },
        effectiveEnabled: Boolean(eff?.enabled ?? true),
      }
    })
  } catch (err) {
    ElMessage.error(errMsg(err))
  } finally {
    rulesLoading.value = false
  }
}

function isDirty(row: RuleRow): boolean {
  if (row.enabled !== row.initialEnabled) return true
  if (row.level !== row.initialLevel) return true
  return Object.keys(row.params).some((key) => row.params[key] !== row.initialParams[key])
}

function dirtyRows(): RuleRow[] {
  return ruleRows.value.filter(isDirty)
}

/** 写回后端；后端 PUT 无法把 level 改回空，因此「继承」时先清除覆盖再重建 */
async function persistRule(row: RuleRow) {
  const diff: Record<string, any> = {}
  let hasDiff = false
  for (const key of Object.keys(row.params)) {
    if (row.params[key] !== row.initialParams[key]) {
      diff[key] = row.params[key]
      hasDiff = true
    }
  }

  const level: Severity | null = row.level === 'inherit' ? null : row.level
  const fullInherit = row.enabled === null && level === null && !hasDiff
  if (fullInherit) {
    await clearTargetRule(targetId.value, row.ruleKey)
    return
  }

  if (level === null) {
    // 后端 PUT 忽略 null，无法把级别改回「继承」，先清除覆盖再重建
    await clearTargetRule(targetId.value, row.ruleKey)
    await setTargetRule(targetId.value, row.ruleKey, {
      enabled: row.enabled,
      params: hasDiff ? diff : null,
    })
    return
  }

  await setTargetRule(targetId.value, row.ruleKey, {
    enabled: row.enabled,
    level,
    params: hasDiff ? diff : null,
  })
}

async function saveRule(row: RuleRow) {
  try {
    await persistRule(row)
    ElMessage.success('规则覆盖已保存')
    await loadRules()
  } catch (err) {
    ElMessage.error(errMsg(err))
  }
}

async function resetRule(row: RuleRow) {
  try {
    await ElMessageBox.confirm(
      `确定要让规则「${row.title}」恢复继承全局配置吗？该目标上的级别与阈值覆盖都会被清除。`,
      '恢复继承',
      { type: 'warning', confirmButtonText: '恢复继承', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await clearTargetRule(targetId.value, row.ruleKey)
    ElMessage.success('已恢复继承全局配置')
    await loadRules()
  } catch (err) {
    ElMessage.error(errMsg(err))
  }
}

async function saveAllRules() {
  const dirty = dirtyRows()
  if (!dirty.length) {
    ElMessage.info('没有需要保存的修改')
    return
  }
  batchSaving.value = true
  try {
    for (const row of dirty) {
      await persistRule(row)
    }
    ElMessage.success(`已保存 ${dirty.length} 条规则覆盖`)
    await loadRules()
  } catch (err) {
    ElMessage.error(errMsg(err))
  } finally {
    batchSaving.value = false
  }
}

// ------------------------------------------------------------------ 运行历史

const runs = ref<InspectionRun[]>([])
const runsTotal = ref(0)
const runsPage = ref(1)
const runsSize = ref(20)
const runsLoading = ref(false)

async function loadRuns() {
  runsLoading.value = true
  try {
    const res = await listInspections({
      target_id: targetId.value,
      page: runsPage.value,
      size: runsSize.value,
    })
    runs.value = res.items ?? []
    runsTotal.value = typeof res.total === 'number' ? res.total : runs.value.length
  } catch (err) {
    ElMessage.error(errMsg(err))
  } finally {
    runsLoading.value = false
  }
}

function onRunsPage(value: number) {
  runsPage.value = value
  void loadRuns()
}

function onRunsSize(value: number) {
  runsSize.value = value
  runsPage.value = 1
  void loadRuns()
}

function goRun(row: InspectionRun) {
  router.push(`/inspections/${row.id}`)
}

// ------------------------------------------------------------------ 标签页

const activeTab = ref('overview')

function onTabChange(name: string | number) {
  if (name === 'rules' && !ruleRows.value.length) void loadRules()
  if (name === 'runs' && !runs.value.length) void loadRuns()
  if (name === 'schedule') void loadSchedule()
}

onMounted(async () => {
  await loadTarget()
  void loadSchedule()
  void loadCapabilities()
})
</script>

<template>
  <div class="vi-page">
    <div class="vi-page-header">
      <h2 class="vi-page-title">
        {{ target ? target.name : '目标详情' }}
        <span v-if="target" class="vi-muted vi-mono">{{ target.host }}:{{ target.port }}</span>
      </h2>
      <div class="vi-toolbar">
        <el-button @click="router.push('/targets')">返回列表</el-button>
      </div>
    </div>

    <el-tabs v-model="activeTab" @tab-change="onTabChange">
      <!-- ---------------------------------------------------------- 概览 -->
      <el-tab-pane label="概览" name="overview">
        <div class="vi-card" v-loading="overviewLoading">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="名称">{{ target?.name ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="地址">
              <span class="vi-mono">{{ target ? `${target.host}:${target.port}` : '-' }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="账号">{{ target?.username ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="启用">
              <el-tag :type="target?.is_enabled ? 'success' : 'info'" size="small" effect="light">
                {{ target?.is_enabled ? '启用' : '禁用' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="校验 TLS">
              {{ target?.verify_tls ? '是' : '否' }}
            </el-descriptions-item>
            <el-descriptions-item label="已存口令">
              {{ target?.has_password ? '是' : '否' }}
            </el-descriptions-item>
            <el-descriptions-item label="创建时间">
              {{ formatDateTime(target?.created_at) }}
            </el-descriptions-item>
            <el-descriptions-item label="更新时间">
              {{ formatDateTime(target?.updated_at) }}
            </el-descriptions-item>
            <el-descriptions-item label="描述" :span="2">
              {{ target?.description || '无' }}
            </el-descriptions-item>
          </el-descriptions>
        </div>

        <div class="vi-card vi-card-gap">
          <div class="vi-card-header">
            <span class="vi-card-title">能力探测</span>
            <div class="vi-toolbar">
              <span class="vi-muted">
                探测结果缓存 1 小时，最近探测时间：{{ formatDateTime(capsCheckedAt) }}
              </span>
              <el-button
                v-if="store.canOperate"
                type="primary"
                :loading="testing"
                @click="testConnectionNow"
              >
                测试连通性
              </el-button>
            </div>
          </div>
          <el-table :data="capabilities" v-loading="capsLoading" size="small">
            <el-table-column label="端点" min-width="260">
              <template #default="{ row }">
                <span class="vi-mono">{{ row.path }}</span>
              </template>
            </el-table-column>
            <el-table-column label="可用" width="90">
              <template #default="{ row }">
                <el-tag :type="row.available ? 'success' : 'warning'" size="small" effect="light">
                  {{ row.available ? '可用' : '不可用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="说明" min-width="160">
              <template #default="{ row }">
                <span class="vi-muted">{{ row.description || '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="错误" min-width="220">
              <template #default="{ row }">
                <span :class="row.error ? 'vi-error-text' : 'vi-muted'">{{ row.error || '-' }}</span>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

      <!-- ---------------------------------------------------------- 排期 -->
      <el-tab-pane label="排期" name="schedule">
        <div class="vi-card">
          <el-form label-width="110px">
            <el-form-item label="Cron 表达式">
              <el-input
                v-model="scheduleCron"
                placeholder="5 段标准 cron，例如 0 2 * * *（分 时 日 月 周）"
                style="max-width: 420px"
              />
            </el-form-item>
            <el-form-item label="时区">
              <el-input
                v-model="scheduleTimezone"
                placeholder="Asia/Shanghai"
                style="max-width: 420px"
              />
            </el-form-item>
            <el-form-item label="启用排期">
              <el-switch v-model="scheduleEnabled" />
            </el-form-item>
            <el-form-item>
              <el-button
                v-if="store.canOperate"
                type="primary"
                :loading="scheduleSaving"
                @click="saveSchedule"
              >
                保存排期
              </el-button>
            </el-form-item>
          </el-form>
          <p class="vi-muted vi-note">
            说明：cron 为 5 段标准 cron 表达式（分 时 日 月 周），需与时区配合使用；
            排期的权威数据保存在 MySQL 中，保存后调度器会重新注册该目标的作业。
          </p>
        </div>
      </el-tab-pane>

      <!-- ------------------------------------------------------ 规则覆盖 -->
      <el-tab-pane label="规则覆盖" name="rules">
        <div class="vi-card">
          <div class="vi-card-header">
            <span class="vi-card-title">目标级规则覆盖</span>
            <div class="vi-toolbar">
              <el-button
                v-if="store.canOperate"
                type="primary"
                :loading="batchSaving"
                @click="saveAllRules"
              >
                批量保存
              </el-button>
              <el-button @click="loadRules">刷新</el-button>
            </div>
          </div>
          <p class="vi-muted vi-note">
            未覆盖的规则继承全局配置（全局配置再回落到规则默认值）；修改后点击单条「保存」，
            或用「批量保存」一次性写入所有改动。
          </p>
          <el-table :data="ruleRows" v-loading="rulesLoading" size="small">
            <el-table-column label="规则" min-width="220">
              <template #default="{ row }">
                <div :title="row.description">{{ row.title }}</div>
                <div class="vi-mono vi-muted">{{ row.ruleKey }}</div>
              </template>
            </el-table-column>
            <el-table-column label="类别" width="110">
              <template #default="{ row }">{{ categoryLabel(row.category) }}</template>
            </el-table-column>
            <el-table-column label="启用" width="150">
              <template #default="{ row }">
                <div class="vi-rule-enabled">
                  <el-switch
                    :model-value="row.enabled ?? row.effectiveEnabled"
                    :disabled="!store.canOperate"
                    @update:model-value="(value: boolean | string | number) => (row.enabled = Boolean(value))"
                  />
                  <el-tag
                    v-if="row.enabled === null"
                    size="small"
                    type="info"
                    effect="plain"
                    class="vi-rule-inherit"
                  >
                    继承
                  </el-tag>
                  <el-button
                    v-else
                    link
                    size="small"
                    :disabled="!store.canOperate"
                    @click="row.enabled = null"
                  >
                    继承
                  </el-button>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="级别" width="140">
              <template #default="{ row }">
                <el-select
                  v-model="row.level"
                  size="small"
                  :disabled="!store.canOperate"
                  style="width: 110px"
                >
                  <el-option
                    v-for="opt in LEVEL_OPTIONS"
                    :key="opt.value"
                    :label="opt.label"
                    :value="opt.value"
                  />
                </el-select>
                <div class="vi-muted vi-hint">默认：{{ LEVEL_LABELS[row.defaultLevel] }}</div>
              </template>
            </el-table-column>
            <el-table-column label="参数" min-width="240">
              <template #default="{ row }">
                <div v-if="!row.schema.length" class="vi-muted">无参数</div>
                <div
                  v-for="param in row.schema"
                  :key="param.key"
                  class="vi-rule-param"
                >
                  <span class="vi-rule-param-label">{{ param.label }}</span>
                  <el-input
                    v-if="param.type === 'string'"
                    v-model="row.params[param.key]"
                    size="small"
                    :placeholder="param.placeholder"
                    style="width: 160px"
                  />
                  <el-input-number
                    v-else-if="param.type === 'number'"
                    v-model="row.params[param.key]"
                    size="small"
                    :min="param.min"
                    :max="param.max"
                    controls-position="right"
                    style="width: 160px"
                  />
                  <el-switch
                    v-else-if="param.type === 'boolean'"
                    v-model="row.params[param.key]"
                    size="small"
                  />
                </div>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button
                  v-if="store.canOperate"
                  link
                  type="primary"
                  size="small"
                  :disabled="!isDirty(asRow<RuleRow>(row))"
                  @click="saveRule(asRow<RuleRow>(row))"
                >
                  保存
                </el-button>
                <el-button
                  v-if="store.canOperate"
                  link
                  type="warning"
                  size="small"
                  @click="resetRule(asRow<RuleRow>(row))"
                >
                  恢复继承
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

      <!-- ------------------------------------------------------ 运行历史 -->
      <el-tab-pane label="运行历史" name="runs">
        <div class="vi-card">
          <el-table
            :data="runs"
            v-loading="runsLoading"
            row-key="id"
            @row-click="goRun"
          >
            <el-table-column label="运行 ID" prop="id" width="100" />
            <el-table-column label="状态" width="110">
              <template #default="{ row }">
                <StatusTag kind="run" :status="row.status" />
              </template>
            </el-table-column>
            <el-table-column label="开始时间" min-width="170">
              <template #default="{ row }">{{ formatDateTime(row.started_at) }}</template>
            </el-table-column>
            <el-table-column label="耗时" width="120">
              <template #default="{ row }">{{ formatDuration(row.duration_ms) }}</template>
            </el-table-column>
            <el-table-column label="严重" width="80" align="center">
              <template #default="{ row }">{{ row.findings_critical }}</template>
            </el-table-column>
            <el-table-column label="警告" width="80" align="center">
              <template #default="{ row }">{{ row.findings_warn }}</template>
            </el-table-column>
            <el-table-column label="提示" width="80" align="center">
              <template #default="{ row }">{{ row.findings_info }}</template>
            </el-table-column>
            <el-table-column label="错误信息" min-width="200">
              <template #default="{ row }">
                <span :class="row.error_message ? 'vi-error-text' : 'vi-muted'">
                  {{ row.error_message || '-' }}
                </span>
              </template>
            </el-table-column>
          </el-table>
          <el-pagination
            class="vi-pagination"
            :current-page="runsPage"
            :page-size="runsSize"
            :total="runsTotal"
            :page-sizes="[20, 50, 100, 200]"
            layout="total, sizes, prev, pager, next, jumper"
            background
            @current-change="onRunsPage"
            @size-change="onRunsSize"
          />
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 连通性测试结果 -->
    <el-dialog v-model="testVisible" title="连通性测试" width="640px">
      <template v-if="testResult">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="结果">
            <el-tag :type="testResult.ok ? 'success' : 'danger'" size="small" effect="light">
              {{ testResult.ok ? '连通成功' : '连通失败' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="服务器时间">
            {{ formatDateTime(testResult.server_time) }}
          </el-descriptions-item>
          <el-descriptions-item label="服务器时区">
            {{ testResult.iana_tz || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="错误信息">
            <span :class="testResult.error ? 'vi-error-text' : 'vi-muted'">
              {{ testResult.error || '无' }}
            </span>
          </el-descriptions-item>
        </el-descriptions>
        <div class="vi-card-title vi-card-gap">服务器信息</div>
        <JsonViewer :data="testResult.server" />
      </template>
      <template #footer>
        <el-button @click="testVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.vi-card-gap {
  margin-top: 16px;
}

.vi-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.vi-card-title {
  font-weight: 600;
}

.vi-note {
  font-size: 12px;
  margin: 0 0 12px;
  line-height: 1.7;
}

.vi-rule-enabled {
  display: flex;
  align-items: center;
  gap: 8px;
}

.vi-rule-param {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.vi-rule-param-label {
  min-width: 120px;
  color: var(--vi-text-muted);
  font-size: 12px;
}

.vi-hint {
  font-size: 12px;
  line-height: 1.4;
  margin-top: 2px;
}

.vi-pagination {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}

.vi-error-text {
  color: #f56c6c;
}
</style>
