<script setup lang="ts">
/**
 * 巡检规则：全局规则配置。
 *
 * 数据来自两处接口：
 *   GET /rules         → 规则目录（rule_key / category / title / 默认级别 / 参数定义）
 *   GET /rules/config  → 全局配置（enabled / level / params，可能为空表示沿用默认）
 * 两者按 rule_key 合并后渲染成一张可编辑的表。
 *
 * 说明：这里的级别与阈值是「全局默认」，单个目标可以在 目标详情 → 规则覆盖 里单独调整。
 */
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listRuleCatalogue, listRuleConfig, resetRules, updateRule } from '@/api'
import type { RuleCatalogueItem, RuleConfigItem, RuleParamSchema, Severity } from '@/api/types'
import RuleForm from '@/components/RuleForm.vue'
import SeverityTag from '@/components/SeverityTag.vue'
import { useUserStore } from '@/stores/user'
import { asRow } from '@/utils/table'

const store = useUserStore()

interface RuleRow {
  rule_key: string
  category: string
  title: string
  description: string
  default_level: Severity
  param_schema: RuleParamSchema[]
  default_params: Record<string, unknown>
  enabled: boolean
  /** 空字符串表示「继承默认级别」 */
  level: Severity | ''
  params: Record<string, unknown>
  /** 保存前的快照，用于判断是否被改动 */
  snapshot: string
}

/** 类别 key → 中文名 */
const CATEGORY_LABELS: Record<string, string> = {
  server: '服务器',
  license: '许可证',
  job: '作业',
  'restore-point': '还原点',
  repository: '存储库',
  proxy: '代理服务器',
  'managed-server': '受管服务器',
  'backup-object': '备份对象',
}

/** 当前级别可选项；空字符串表示沿用规则默认级别 */
const LEVEL_OPTIONS: { label: string; value: Severity | '' }[] = [
  { label: '继承', value: '' },
  { label: '严重', value: 'critical' },
  { label: '警告', value: 'warn' },
  { label: '提示', value: 'info' },
  { label: '正常', value: 'ok' },
]

const rows = ref<RuleRow[]>([])
const loading = ref(false)
const saving = ref(false)
const keyword = ref('')
const category = ref('')

function errorText(err: unknown, fallback: string): string {
  return err instanceof Error ? err.message : fallback
}

/** 稳定序列化：键排序后比较，避免对象键顺序不同造成的「假改动」 */
function stableStringify(value: unknown): string {
  if (value === null || typeof value !== 'object') return JSON.stringify(value) ?? 'null'
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(',')}]`
  const obj = value as Record<string, unknown>
  return `{${Object.keys(obj)
    .sort()
    .map((key) => `${JSON.stringify(key)}:${stableStringify(obj[key])}`)
    .join(',')}}`
}

function currentSnapshot(row: RuleRow): string {
  return stableStringify({
    enabled: row.enabled,
    level: row.level,
    params: row.params,
  })
}

function isDirty(row: RuleRow): boolean {
  return currentSnapshot(row) !== row.snapshot
}

/** 目录与全局配置按 rule_key 合并 */
function buildRows(catalogue: RuleCatalogueItem[], config: RuleConfigItem[]): RuleRow[] {
  const configMap = new Map<string, RuleConfigItem>()
  for (const item of config) configMap.set(item.rule_key, item)

  return catalogue.map((item) => {
    const cfg = configMap.get(item.rule_key)
    const enabled = cfg?.enabled ?? true
    const level = (cfg?.level ?? null) as Severity | ''
    const params = { ...(item.default_params ?? {}), ...(cfg?.params ?? {}) }
    const row: RuleRow = {
      rule_key: item.rule_key,
      category: item.category,
      title: item.title,
      description: item.description,
      default_level: item.default_level,
      param_schema: item.param_schema ?? [],
      default_params: item.default_params ?? {},
      enabled,
      level,
      params,
      snapshot: '',
    }
    row.snapshot = currentSnapshot(row)
    return row
  })
}

const categories = computed(() => {
  const seen = new Set<string>()
  for (const row of rows.value) seen.add(row.category)
  return [...seen]
})

const filteredRows = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return rows.value.filter((row) => {
    if (category.value && row.category !== category.value) return false
    if (!kw) return true
    return (
      row.title.toLowerCase().includes(kw) ||
      row.rule_key.toLowerCase().includes(kw) ||
      (row.description || '').toLowerCase().includes(kw)
    )
  })
})

const dirtyCount = computed(() => rows.value.filter(isDirty).length)

function categoryLabel(key: string): string {
  return CATEGORY_LABELS[key] ?? key
}

async function load() {
  loading.value = true
  try {
    const [catalogue, config] = await Promise.all([listRuleCatalogue(), listRuleConfig()])
    rows.value = buildRows(catalogue.items ?? [], config.items ?? [])
  } catch (err) {
    ElMessage.error(errorText(err, '加载规则配置失败'))
  } finally {
    loading.value = false
  }
}

/** 保存单行 */
async function saveRow(row: RuleRow): Promise<boolean> {
  if (!store.canOperate) {
    ElMessage.warning('当前角色无权修改规则配置')
    return false
  }
  try {
    await updateRule(row.rule_key, {
      enabled: row.enabled,
      level: row.level === '' ? null : row.level,
      params: { ...row.params },
    })
    row.snapshot = currentSnapshot(row)
    return true
  } catch (err) {
    ElMessage.error(errorText(err, `保存规则「${row.title}」失败`))
    return false
  }
}

async function onSaveRow(row: RuleRow) {
  const ok = await saveRow(row)
  if (ok) ElMessage.success(`规则「${row.title}」已保存`)
}

/** 依次保存所有被改动的行 */
async function onSaveAll() {
  if (!store.canOperate) {
    ElMessage.warning('当前角色无权修改规则配置')
    return
  }
  const dirty = rows.value.filter(isDirty)
  if (!dirty.length) {
    ElMessage.info('没有需要保存的修改')
    return
  }
  saving.value = true
  let failed = 0
  for (const row of dirty) {
    const ok = await saveRow(row)
    if (!ok) failed += 1
  }
  saving.value = false
  if (!failed) ElMessage.success(`已保存 ${dirty.length} 条规则配置`)
}

/** 把某行的参数恢复到规则默认参数 */
function onResetParams(row: RuleRow) {
  row.params = { ...row.default_params }
}

async function onResetRules() {
  try {
    await ElMessageBox.confirm(
      '恢复默认会清除所有全局规则配置的修改（启用状态、级别与阈值参数），确定继续吗？',
      '恢复默认',
      { type: 'warning', confirmButtonText: '恢复默认', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await resetRules()
    ElMessage.success('全局规则配置已恢复默认')
    await load()
  } catch (err) {
    ElMessage.error(errorText(err, '恢复默认失败'))
  }
}

onMounted(load)
</script>

<template>
  <div class="vi-page">
    <div class="vi-page-header">
      <h2 class="vi-page-title">巡检规则</h2>
      <div class="vi-toolbar">
        <el-select v-model="category" placeholder="全部类别" style="width: 160px" clearable>
          <el-option
            v-for="key in categories"
            :key="key"
            :label="categoryLabel(key)"
            :value="key"
          />
        </el-select>
        <el-input
          v-model="keyword"
          placeholder="搜索规则名称或 rule_key"
          style="width: 240px"
          clearable
        />
        <el-button @click="load">刷新</el-button>
        <el-button
          type="primary"
          :loading="saving"
          :disabled="!store.canOperate || dirtyCount === 0"
          @click="onSaveAll"
        >
          保存全部<template v-if="dirtyCount">（{{ dirtyCount }}）</template>
        </el-button>
        <el-button type="danger" plain :disabled="!store.canOperate" @click="onResetRules">
          恢复默认
        </el-button>
      </div>
    </div>

    <el-alert
      type="info"
      :closable="false"
      show-icon
      class="rule-note"
      title="此处配置的是规则的全局默认值（级别与阈值参数）；单个目标可在「目标详情 → 规则覆盖」中单独覆盖。"
    />

    <div class="vi-card">
      <el-table v-loading="loading" :data="filteredRows" border stripe style="width: 100%">
        <el-table-column label="规则" min-width="240">
          <template #default="{ row }">
            <div class="rule-title">{{ row.title }}</div>
            <div class="vi-mono vi-muted">{{ row.rule_key }}</div>
            <div v-if="row.description" class="vi-muted rule-desc">{{ row.description }}</div>
          </template>
        </el-table-column>
        <el-table-column label="类别" width="110" align="center">
          <template #default="{ row }">{{ categoryLabel(row.category) }}</template>
        </el-table-column>
        <el-table-column label="默认级别" width="100" align="center">
          <template #default="{ row }">
            <SeverityTag :level="row.default_level" />
          </template>
        </el-table-column>
        <el-table-column label="当前级别" width="130" align="center">
          <template #default="{ row }">
            <el-select v-model="row.level" size="small" style="width: 100%">
              <el-option
                v-for="opt in LEVEL_OPTIONS"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="启用" width="80" align="center">
          <template #default="{ row }">
            <el-switch v-model="row.enabled" :disabled="!store.canOperate" />
          </template>
        </el-table-column>
        <el-table-column label="参数" min-width="240">
          <template #default="{ row }">
            <RuleForm :schema="row.param_schema" v-model="row.params" />
            <el-button
              link
              type="primary"
              class="rule-reset-params"
              :disabled="!store.canOperate || row.param_schema.length === 0"
              @click="onResetParams(asRow<RuleRow>(row))"
            >
              恢复默认参数
            </el-button>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="90" align="center" fixed="right">
          <template #default="{ row }">
            <el-button
              link
              type="primary"
              :disabled="!store.canOperate || !isDirty(asRow<RuleRow>(row))"
              @click="onSaveRow(asRow<RuleRow>(row))"
            >
              保存
            </el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="没有匹配的规则" />
        </template>
      </el-table>
    </div>
  </div>
</template>

<style scoped>
.rule-note {
  margin-bottom: 12px;
}

.rule-title {
  font-weight: 600;
}

.rule-desc {
  font-size: 12px;
  margin-top: 2px;
}

.rule-reset-params {
  margin-top: 4px;
}
</style>
