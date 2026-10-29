<script setup lang="ts">
/**
 * 发现项：跨巡检轮次的问题清单，支持确认 / 解决 / 批量确认与历史事件回溯。
 */
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  acknowledgeFinding,
  bulkAcknowledge,
  findingsSummary,
  getFindingEvents,
  listFindings,
  listTargets,
  resolveFinding,
} from '@/api'
import type { Finding, FindingEvent, Target } from '@/api/types'
import SeverityTag from '@/components/SeverityTag.vue'
import StatusTag from '@/components/StatusTag.vue'
import { formatDateTime } from '@/utils/format'
import { asRow } from '@/utils/table'
import { versionLabel } from '@/utils/version'
import { useUserStore } from '@/stores/user'

const store = useUserStore()

/** 级别筛选项；空字符串表示不限 */
const LEVEL_OPTIONS = [
  { label: '全部级别', value: '' },
  { label: '严重', value: 'critical' },
  { label: '警告', value: 'warn' },
  { label: '提示', value: 'info' },
]

/** 状态筛选项；空字符串表示不限 */
const STATUS_OPTIONS = [
  { label: '全部状态', value: '' },
  { label: '待处理', value: 'open' },
  { label: '已确认', value: 'acknowledged' },
  { label: '已解决', value: 'resolved' },
]

const targets = ref<Target[]>([])

function targetVersionLabel(target: Target): string {
  return versionLabel(target.detected_version, target.version_preference)
}

function targetOptionLabel(target: Target): string {
  return `${target.name} · ${targetVersionLabel(target)}`
}

function targetLabel(id: number): string {
  const hit = targets.value.find((t) => t.id === id)
  return hit ? `${hit.name} · ${targetVersionLabel(hit)}` : `#${id}`
}

const rows = ref<Finding[]>([])
const total = ref(0)
const loading = ref(false)
const selected = ref<Finding[]>([])

const summary = ref<{ by_level: Record<string, number>; by_status: Record<string, number> }>({
  by_level: {},
  by_status: {},
})

const filters = reactive({
  target_id: '' as number | '',
  level: '' as string,
  status: '' as string,
  category: '',
  keyword: '',
})
const page = ref(1)
const size = ref(20)

// ---- 详情抽屉 ----
const drawerVisible = ref(false)
const current = ref<Finding | null>(null)
const events = ref<FindingEvent[]>([])
const eventsLoading = ref(false)

function errorText(err: unknown, fallback: string): string {
  return err instanceof Error ? err.message : fallback
}

function levelCount(level: string): number {
  return summary.value.by_level?.[level] ?? 0
}

function statusCount(status: string): number {
  return summary.value.by_status?.[status] ?? 0
}

async function loadTargets() {
  try {
    const res = await listTargets()
    targets.value = res.items ?? []
  } catch (err) {
    ElMessage.error(errorText(err, '加载目标列表失败'))
  }
}

async function loadSummary() {
  try {
    const params = filters.target_id === '' ? undefined : { target_id: filters.target_id }
    const res = await findingsSummary(params)
    summary.value = {
      by_level: res.by_level ?? {},
      by_status: res.by_status ?? {},
    }
  } catch (err) {
    ElMessage.error(errorText(err, '加载发现项统计失败'))
  }
}

async function load() {
  loading.value = true
  try {
    const params: {
      target_id?: number
      level?: string
      status?: string
      category?: string
      keyword?: string
      page: number
      size: number
    } = { page: page.value, size: size.value }
    if (filters.target_id !== '') params.target_id = filters.target_id
    if (filters.level) params.level = filters.level
    if (filters.status) params.status = filters.status
    if (filters.category.trim()) params.category = filters.category.trim()
    if (filters.keyword.trim()) params.keyword = filters.keyword.trim()

    const res = await listFindings(params)
    rows.value = res.items ?? []
    total.value = res.total ?? 0
    selected.value = []
  } catch (err) {
    ElMessage.error(errorText(err, '加载发现项失败'))
  } finally {
    loading.value = false
  }
}

async function refreshAll() {
  await Promise.all([load(), loadSummary()])
}

function onSearch() {
  page.value = 1
  refreshAll()
}

function onReset() {
  filters.target_id = ''
  filters.level = ''
  filters.status = ''
  filters.category = ''
  filters.keyword = ''
  page.value = 1
  refreshAll()
}

function onPageChange(next: number) {
  page.value = next
  load()
}

function onSizeChange(next: number) {
  size.value = next
  page.value = 1
  load()
}

function onSelectionChange(list: Finding[]) {
  selected.value = list
}

async function handleAcknowledge(row: Finding) {
  if (!store.canOperate) {
    ElMessage.warning('当前角色无权执行该操作')
    return
  }
  try {
    await acknowledgeFinding(row.id)
    ElMessage.success('已确认')
    await refreshAll()
  } catch (err) {
    ElMessage.error(errorText(err, '确认发现项失败'))
  }
}

async function handleResolve(row: Finding) {
  if (!store.canOperate) {
    ElMessage.warning('当前角色无权执行该操作')
    return
  }
  try {
    await resolveFinding(row.id)
    ElMessage.success('已解决')
    await refreshAll()
  } catch (err) {
    ElMessage.error(errorText(err, '解决发现项失败'))
  }
}

async function handleBulkAck() {
  if (!store.canOperate) {
    ElMessage.warning('当前角色无权执行该操作')
    return
  }
  const ids = selected.value.map((item) => item.id)
  if (!ids.length) {
    ElMessage.warning('请先选择要确认的发现项')
    return
  }
  try {
    const res = await bulkAcknowledge({ finding_ids: ids })
    // 后端返回 { acknowledged: n }，兼容 api 层声明的 { updated: n }
    const raw = res as { updated?: number; acknowledged?: number }
    const count = raw.updated ?? raw.acknowledged ?? ids.length
    ElMessage.success(`已确认 ${count} 项`)
    await refreshAll()
  } catch (err) {
    ElMessage.error(errorText(err, '批量确认失败'))
  }
}

async function openDetail(row: Finding) {
  current.value = row
  events.value = []
  drawerVisible.value = true
  eventsLoading.value = true
  try {
    const res = await getFindingEvents(row.id)
    events.value = res.items ?? []
  } catch (err) {
    ElMessage.error(errorText(err, '加载历史事件失败'))
  } finally {
    eventsLoading.value = false
  }
}

onMounted(async () => {
  await loadTargets()
  await refreshAll()
})
</script>

<template>
  <div class="vi-page">
    <div class="vi-page-header">
      <h2 class="vi-page-title">发现项</h2>
      <div class="vi-toolbar">
        <el-button :disabled="!store.canOperate" @click="handleBulkAck">
          批量确认
          <template v-if="selected.length">（{{ selected.length }}）</template>
        </el-button>
        <el-button @click="refreshAll">刷新</el-button>
      </div>
    </div>

    <div class="vi-card summary-card">
      <div class="summary-group">
        <span class="summary-title">按级别</span>
        <span class="chip chip-critical">严重 {{ levelCount('critical') }}</span>
        <span class="chip chip-warn">警告 {{ levelCount('warn') }}</span>
        <span class="chip chip-info">提示 {{ levelCount('info') }}</span>
      </div>
      <div class="summary-group">
        <span class="summary-title">按状态</span>
        <span class="chip">待处理 {{ statusCount('open') }}</span>
        <span class="chip chip-warn">已确认 {{ statusCount('acknowledged') }}</span>
        <span class="chip chip-ok">已解决 {{ statusCount('resolved') }}</span>
      </div>
    </div>

    <div class="vi-card filter-card">
      <div class="vi-toolbar">
        <el-select
          v-model="filters.target_id"
          placeholder="全部目标"
          style="width: 190px"
        >
          <el-option label="全部目标" value="" />
          <el-option v-for="t in targets" :key="t.id" :label="targetOptionLabel(t)" :value="t.id" />
        </el-select>
        <el-select v-model="filters.level" placeholder="全部级别" style="width: 130px">
          <el-option
            v-for="opt in LEVEL_OPTIONS"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
        <el-select v-model="filters.status" placeholder="全部状态" style="width: 130px">
          <el-option
            v-for="opt in STATUS_OPTIONS"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
        <el-input
          v-model="filters.category"
          placeholder="类别"
          clearable
          style="width: 150px"
          @keyup.enter="onSearch"
        />
        <el-input
          v-model="filters.keyword"
          placeholder="关键字"
          clearable
          style="width: 180px"
          @keyup.enter="onSearch"
        />
        <el-button type="primary" @click="onSearch">查询</el-button>
        <el-button @click="onReset">重置</el-button>
      </div>
    </div>

    <div class="vi-card">
      <el-table
        v-loading="loading"
        :data="rows"
        border
        stripe
        style="width: 100%"
        @selection-change="onSelectionChange"
      >
        <el-table-column type="selection" width="45" align="center" />
        <el-table-column prop="id" label="ID" width="80" align="center">
          <template #default="{ row }">
            <span class="vi-mono">#{{ row.id }}</span>
          </template>
        </el-table-column>
        <el-table-column label="级别" width="90" align="center">
          <template #default="{ row }">
            <SeverityTag :level="row.level" />
          </template>
        </el-table-column>
        <el-table-column label="规则" width="180">
          <template #default="{ row }">
            <span class="vi-mono">{{ row.rule_key }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="category" label="类别" width="140" />
        <el-table-column prop="subject" label="对象" min-width="160" />
        <el-table-column prop="message" label="说明" min-width="240" />
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <StatusTag kind="finding" :status="row.status" />
          </template>
        </el-table-column>
        <el-table-column prop="occurrences" label="次数" width="80" align="center" />
        <el-table-column label="首次发现" width="170">
          <template #default="{ row }">{{ formatDateTime(row.first_seen_at) }}</template>
        </el-table-column>
        <el-table-column label="最近发现" width="170">
          <template #default="{ row }">{{ formatDateTime(row.last_seen_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="170" align="center" fixed="right">
          <template #default="{ row }">
            <el-button
              link
              type="primary"
              :disabled="!store.canOperate"
              @click="handleAcknowledge(asRow<Finding>(row))"
            >
              确认
            </el-button>
            <el-button
              link
              type="success"
              :disabled="!store.canOperate"
              @click="handleResolve(asRow<Finding>(row))"
            >
              解决
            </el-button>
            <el-button link type="info" @click="openDetail(asRow<Finding>(row))">详情</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无发现项" />
        </template>
      </el-table>

      <div class="pager">
        <el-pagination
          :current-page="page"
          :page-size="size"
          :page-sizes="[10, 20, 50, 100]"
          :total="total"
          layout="total, sizes, prev, pager, next"
          background
          @current-change="onPageChange"
          @size-change="onSizeChange"
        />
      </div>
    </div>

    <el-drawer v-model="drawerVisible" title="发现项详情" size="620px">
      <template v-if="current">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="ID">
            <span class="vi-mono">#{{ current.id }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="目标">
            {{ targetLabel(current.target_id) }}
          </el-descriptions-item>
          <el-descriptions-item label="级别">
            <SeverityTag :level="current.level" />
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <StatusTag kind="finding" :status="current.status" />
          </el-descriptions-item>
          <el-descriptions-item label="规则">
            <span class="vi-mono">{{ current.rule_key }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="类别">{{ current.category }}</el-descriptions-item>
          <el-descriptions-item label="对象" :span="2">
            {{ current.subject }}
          </el-descriptions-item>
          <el-descriptions-item label="说明" :span="2">{{ current.message }}</el-descriptions-item>
          <el-descriptions-item label="指标">
            {{ current.metric_value ?? '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="阈值">
            {{ current.threshold_value ?? '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="次数">{{ current.occurrences }}</el-descriptions-item>
          <el-descriptions-item label="指纹">
            <span class="vi-mono">{{ current.fingerprint }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="首次发现">
            {{ formatDateTime(current.first_seen_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="最近发现">
            {{ formatDateTime(current.last_seen_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="最近运行">
            <span class="vi-mono">
              {{ current.last_run_id ? `#${current.last_run_id}` : '-' }}
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="已解决时间">
            {{ formatDateTime(current.resolved_at) }}
          </el-descriptions-item>
        </el-descriptions>

        <h4 class="drawer-subtitle">历史事件</h4>
        <el-table v-loading="eventsLoading" :data="events" border size="small">
          <el-table-column label="时间" width="170">
            <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="级别" width="90" align="center">
            <template #default="{ row }">
              <SeverityTag :level="row.level" />
            </template>
          </el-table-column>
          <el-table-column label="说明" min-width="200">
            <template #default="{ row }">{{ row.message ?? '-' }}</template>
          </el-table-column>
          <el-table-column label="run_id" width="100" align="center">
            <template #default="{ row }">
              <span class="vi-mono">#{{ row.run_id }}</span>
            </template>
          </el-table-column>
          <template #empty>
            <el-empty description="暂无历史事件" />
          </template>
        </el-table>
      </template>
    </el-drawer>
  </div>
</template>

<style scoped>
.summary-card {
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.summary-group {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.summary-title {
  color: var(--vi-text-muted);
  font-size: 13px;
}

.chip {
  background: #f4f6fa;
  border-radius: 12px;
  padding: 2px 10px;
  font-size: 13px;
  color: var(--vi-text);
}

.chip-critical {
  color: #f56c6c;
  background: #fef0f0;
}

.chip-warn {
  color: #e6a23c;
  background: #fdf6ec;
}

.chip-info {
  color: #409eff;
  background: #ecf5ff;
}

.chip-ok {
  color: #67c23a;
  background: #f0f9eb;
}

.filter-card {
  margin-bottom: 12px;
}

.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

.drawer-subtitle {
  margin: 20px 0 8px;
  font-size: 14px;
  font-weight: 600;
}
</style>
