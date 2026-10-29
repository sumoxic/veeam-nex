/**
 * 操作审计（管理员视角，只读）。
 *
 * 远程操作每一步都会落库，这里按目标 / 状态 / 时间范围回溯全生命周期。
 * 后端审计接口暂不支持时间范围与类型过滤，时间范围随请求带过去并在本地生效。
 */
<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { auditOperations, listTargets } from '@/api'
import type { OperationAudit, OperationStatus, Target } from '@/api/types'
import { useUserStore } from '@/stores/user'
import { formatDateTime, formatDuration } from '@/utils/format'
import { asRow } from '@/utils/table'
import { versionLabel } from '@/utils/version'
import JsonViewer from '@/components/JsonViewer.vue'
import StatusTag from '@/components/StatusTag.vue'

/** 比前端封装的参数多了时间范围，后端会忽略未知查询参数，本地再过滤一次 */
interface AuditQuery {
  target_id?: number
  status?: string
  page?: number
  size?: number
  start_time?: string
  end_time?: string
}

const store = useUserStore()

const STATUS_OPTIONS: { value: OperationStatus; label: string }[] = [
  { value: 'pending', label: '待确认' },
  { value: 'executing', label: '执行中' },
  { value: 'succeeded', label: '成功' },
  { value: 'failed', label: '失败' },
  { value: 'expired', label: '已过期' },
  { value: 'rejected', label: '已拒绝' },
]

function errorText(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

const targets = ref<Target[]>([])
const rows = ref<OperationAudit[]>([])
const total = ref(0)
const loading = ref(false)

const filters = reactive<{
  status?: OperationStatus
  target_id?: number
}>({})
const range = ref<[string, string] | null>(null)
const page = ref(1)
const size = ref(20)

function targetOptionLabel(target: Target): string {
  return `${target.name}（${target.host} · ${versionLabel(
    target.detected_version,
    target.version_preference,
  )}）`
}

function targetName(id: number): string {
  const hit = targets.value.find((t) => t.id === id)
  if (!hit) return `#${id}`
  return `${hit.name}（${hit.host} · ${versionLabel(hit.detected_version, hit.version_preference)}）`
}

/** 后端返回的是无时区 UTC 字符串 */
function toMs(value?: string | null): number {
  if (!value) return NaN
  const normalized = /[zZ]|[+-]\d{2}:?\d{2}$/.test(value) ? value : `${value}Z`
  return new Date(normalized).getTime()
}

/** el-date-picker 给的是本地时间，转成 ISO 传给后端 */
function toIso(local: string): string {
  const d = new Date(local.replace(' ', 'T'))
  return Number.isNaN(d.getTime()) ? local : d.toISOString()
}

function onRangeChange(value: unknown) {
  if (Array.isArray(value) && value.length === 2) {
    range.value = [String(value[0]), String(value[1])]
  } else {
    range.value = null
  }
}

async function loadTargets() {
  try {
    const res = await listTargets()
    targets.value = res.items ?? []
  } catch (err) {
    ElMessage.error(errorText(err))
  }
}

async function load() {
  loading.value = true
  try {
    const query: AuditQuery = {
      target_id: filters.target_id,
      status: filters.status,
      page: page.value,
      size: size.value,
    }
    if (range.value) {
      query.start_time = toIso(range.value[0])
      query.end_time = toIso(range.value[1])
    }
    const res = await auditOperations(query)
    let items = res.items ?? []
    if (range.value) {
      const start = toMs(query.start_time)
      const end = toMs(query.end_time)
      items = items.filter((row) => {
        const ts = toMs(row.created_at)
        return !Number.isNaN(ts) && ts >= start && ts <= end
      })
    }
    rows.value = items
    total.value = res.total ?? items.length
  } catch (err) {
    ElMessage.error(errorText(err))
  } finally {
    loading.value = false
  }
}

function handleFilterChange() {
  page.value = 1
  load()
}

function handleRefresh() {
  page.value = 1
  load()
}

onMounted(() => {
  loadTargets()
  load()
})

// ---------------------------------------------------------------- 详情

const detailVisible = ref(false)
const detailRow = ref<OperationAudit | null>(null)

function openDetail(row: OperationAudit) {
  detailRow.value = row
  detailVisible.value = true
}

/** 从建单到确认之间的耗时 */
function duration(row: OperationAudit): string {
  const start = toMs(row.created_at)
  const end = toMs(row.confirmed_at)
  if (Number.isNaN(start) || Number.isNaN(end)) return '-'
  return formatDuration(end - start)
}

/** 审计接口不返回完整 result，这里给出可读摘要 */
function resultSummary(row: OperationAudit): string {
  if (row.error_message) return `失败：${row.error_message}`
  if (row.vbr_task_id) return `已提交，VBR 任务 ${row.vbr_task_id}`
  if (row.status === 'succeeded') return '执行成功'
  if (row.status === 'rejected') return '已拒绝'
  if (row.status === 'expired') return '令牌过期，未执行'
  if (row.status === 'pending') return '等待确认'
  return '-'
}
</script>

<template>
  <div class="vi-page">
    <div class="vi-page-header">
      <h2 class="vi-page-title">操作审计</h2>
      <div class="vi-toolbar">
        <el-button @click="handleRefresh">刷新</el-button>
      </div>
    </div>

    <el-alert
      v-if="!store.isAdmin"
      type="info"
      :closable="false"
      show-icon
      title="操作审计仅对管理员开放。"
      class="vi-audit-alert"
    />

    <div class="vi-card">
      <div class="vi-toolbar vi-audit-filters">
        <el-select
          v-model="filters.status"
          placeholder="全部状态"
          clearable
          style="width: 140px"
          @change="handleFilterChange"
        >
          <el-option
            v-for="item in STATUS_OPTIONS"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>

        <el-select
          v-model="filters.target_id"
          placeholder="全部目标"
          clearable
          style="width: 220px"
          @change="handleFilterChange"
        >
          <el-option
            v-for="item in targets"
            :key="item.id"
            :label="targetOptionLabel(item)"
            :value="item.id"
          />
        </el-select>

        <el-date-picker
          :model-value="range"
          type="datetimerange"
          range-separator="至"
          start-placeholder="开始时间"
          end-placeholder="结束时间"
          value-format="YYYY-MM-DD HH:mm:ss"
          style="width: 360px"
          @update:model-value="onRangeChange"
        />

        <el-button @click="handleFilterChange">查询</el-button>
      </div>

      <el-table v-loading="loading" :data="rows" border stripe>
        <el-table-column label="请求 ID" min-width="230">
          <template #default="{ row }">
            <span class="vi-mono">{{ row.request_id }}</span>
          </template>
        </el-table-column>

        <el-table-column label="操作类型" min-width="130">
          <template #default="{ row }">
            <span class="vi-mono">{{ row.operation_kind }}</span>
          </template>
        </el-table-column>

        <el-table-column label="目标" min-width="160">
          <template #default="{ row }">{{ targetName(row.target_id) }}</template>
        </el-table-column>

        <el-table-column label="操作人" width="100">
          <template #default="{ row }">{{ row.operator_id ?? '-' }}</template>
        </el-table-column>

        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <StatusTag kind="operation" :status="row.status" />
          </template>
        </el-table-column>

        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>

        <el-table-column label="确认时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.confirmed_at) }}</template>
        </el-table-column>

        <el-table-column label="耗时" width="120">
          <template #default="{ row }">{{ duration(asRow<OperationAudit>(row)) }}</template>
        </el-table-column>

        <el-table-column label="结果摘要" min-width="220">
          <template #default="{ row }">
            <span class="vi-muted">{{ resultSummary(asRow<OperationAudit>(row)) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ row }">
            <el-button link type="info" size="small" @click="openDetail(asRow<OperationAudit>(row))">详情</el-button>
          </template>
        </el-table-column>

        <template #empty>
          <span class="vi-muted">暂无审计记录</span>
        </template>
      </el-table>

      <el-pagination
        v-model:current-page="page"
        v-model:page-size="size"
        class="vi-audit-pager"
        background
        layout="total, sizes, prev, pager, next"
        :page-sizes="[10, 20, 50, 100]"
        :total="total"
        @current-change="load"
        @size-change="handleRefresh"
      />
    </div>

    <el-drawer v-model="detailVisible" title="审计详情" size="560px">
      <div v-if="detailRow" class="vi-audit-detail">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="请求 ID">
            <span class="vi-mono">{{ detailRow.request_id }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="操作类型">
            <span class="vi-mono">{{ detailRow.operation_kind }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="目标">
            {{ targetName(detailRow.target_id) }}
          </el-descriptions-item>
          <el-descriptions-item label="操作人">{{ detailRow.operator_id ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <StatusTag kind="operation" :status="detailRow.status" />
          </el-descriptions-item>
          <el-descriptions-item label="创建时间">
            {{ formatDateTime(detailRow.created_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="确认时间">
            {{ formatDateTime(detailRow.confirmed_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="耗时">{{ duration(detailRow) }}</el-descriptions-item>
          <el-descriptions-item label="令牌有效期至">
            {{ formatDateTime(detailRow.token_expires_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="VBR 任务 ID">
            <span class="vi-mono">{{ detailRow.vbr_task_id || '-' }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="错误">
            <span class="vi-muted">{{ detailRow.error_message || '-' }}</span>
          </el-descriptions-item>
        </el-descriptions>

        <div class="vi-audit-block">
          <div class="vi-muted">预览内容</div>
          <pre class="vi-mono vi-audit-preview">{{ detailRow.preview_text }}</pre>
        </div>

        <div class="vi-audit-block">
          <div class="vi-muted">参数</div>
          <JsonViewer :data="detailRow.params" />
        </div>

        <div class="vi-audit-block">
          <div class="vi-muted">执行结果</div>
          <JsonViewer :data="detailRow.result ?? {}" />
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
.vi-audit-alert {
  margin-bottom: 12px;
}

.vi-audit-filters {
  margin-bottom: 12px;
}

.vi-audit-pager {
  margin-top: 12px;
  justify-content: flex-end;
}

.vi-audit-block {
  margin-top: 14px;
}

.vi-audit-preview {
  margin: 6px 0 0;
  padding: 12px;
  background: #fafbfd;
  border: 1px solid #e8ebf0;
  border-radius: 6px;
  white-space: pre-wrap;
  word-break: break-all;
  line-height: 1.6;
}
</style>
