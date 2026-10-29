<script setup lang="ts">
/**
 * 告警事件：告警投递记录（发送成功 / 失败 / 被去重抑制）。
 *
 * 列表来自 GET /alert-events（支持按状态与级别过滤、分页）。
 * 点击任意一行可以打开抽屉查看事件的完整字段与正文。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { listAlertEvents, retryAlertEvent } from '@/api'
import type { AlertEvent, Severity } from '@/api/types'
import SeverityTag from '@/components/SeverityTag.vue'
import StatusTag from '@/components/StatusTag.vue'
import { formatDateTime } from '@/utils/format'
import { asRow } from '@/utils/table'
import { useUserStore } from '@/stores/user'

const store = useUserStore()

/** 状态筛选项；空字符串表示不限 */
const STATUS_OPTIONS = [
  { label: '全部状态', value: '' },
  { label: '待发送', value: 'pending' },
  { label: '已发送', value: 'sent' },
  { label: '发送失败', value: 'failed' },
  { label: '已抑制', value: 'suppressed' },
]

const LEVEL_OPTIONS: { label: string; value: Severity | '' }[] = [
  { label: '全部级别', value: '' },
  { label: '严重', value: 'critical' },
  { label: '警告', value: 'warn' },
  { label: '提示', value: 'info' },
  { label: '正常', value: 'ok' },
]

/** 事件类型 → 中文 */
const EVENT_TYPE_LABELS: Record<string, string> = {
  raised: '新建',
  resolved: '恢复',
  escalated: '升级',
}

const rows = ref<AlertEvent[]>([])
const total = ref(0)
const loading = ref(false)
const page = ref(1)
const size = ref(20)

const filters = reactive<{ status: string; severity: Severity | '' }>({
  status: '',
  severity: '',
})

const drawerVisible = ref(false)
const current = ref<AlertEvent | null>(null)

function errorText(err: unknown, fallback: string): string {
  return err instanceof Error ? err.message : fallback
}

function eventTypeText(type?: string | null): string {
  if (!type) return '-'
  return EVENT_TYPE_LABELS[type] ?? type
}

async function load() {
  loading.value = true
  try {
    const params: { status?: string; severity?: string; page: number; size: number } = {
      page: page.value,
      size: size.value,
    }
    if (filters.status) params.status = filters.status
    if (filters.severity) params.severity = filters.severity
    const res = await listAlertEvents(params)
    rows.value = res.items ?? []
    total.value = res.total ?? 0
  } catch (err) {
    ElMessage.error(errorText(err, '加载告警事件失败'))
  } finally {
    loading.value = false
  }
}

function onSearch() {
  page.value = 1
  load()
}

function onReset() {
  filters.status = ''
  filters.severity = ''
  page.value = 1
  load()
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

function onRowClick(row: AlertEvent) {
  current.value = row
  drawerVisible.value = true
}

async function onRetry(row: AlertEvent) {
  if (!store.canOperate) {
    ElMessage.warning('当前角色无权重试告警事件')
    return
  }
  try {
    const result = await retryAlertEvent(row.id)
    const info = (result ?? {}) as unknown as Record<string, unknown>
    const sent = typeof info.sent === 'boolean' ? info.sent : true
    if (sent) ElMessage.success(`告警事件 #${row.id} 重试成功`)
    else ElMessage.warning(`告警事件 #${row.id} 重试未成功`)
    await load()
  } catch (err) {
    ElMessage.error(errorText(err, '重试告警事件失败'))
  }
}

const bodyText = computed(() => current.value?.body ?? '')

onMounted(load)
</script>

<template>
  <div class="vi-page">
    <div class="vi-page-header">
      <h2 class="vi-page-title">告警事件</h2>
      <div class="vi-toolbar">
        <el-select v-model="filters.status" placeholder="全部状态" style="width: 140px" @change="onSearch">
          <el-option
            v-for="opt in STATUS_OPTIONS"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
        <el-select
          v-model="filters.severity"
          placeholder="全部级别"
          style="width: 140px"
          @change="onSearch"
        >
          <el-option
            v-for="opt in LEVEL_OPTIONS"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
        <el-button @click="onReset">重置</el-button>
        <el-button @click="load">刷新</el-button>
      </div>
    </div>

    <div class="vi-card">
      <el-table
        v-loading="loading"
        :data="rows"
        border
        stripe
        style="width: 100%"
        @row-click="onRowClick"
      >
        <el-table-column label="ID" width="80" align="center">
          <template #default="{ row }">
            <span class="vi-mono">#{{ row.id }}</span>
          </template>
        </el-table-column>
        <el-table-column label="时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="事件类型" width="100" align="center">
          <template #default="{ row }">{{ eventTypeText(row.event_type) }}</template>
        </el-table-column>
        <el-table-column label="级别" width="90" align="center">
          <template #default="{ row }">
            <SeverityTag :level="row.severity" />
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <StatusTag kind="alert-event" :status="row.status" />
          </template>
        </el-table-column>
        <el-table-column label="去重键" min-width="200">
          <template #default="{ row }">
            <span class="vi-mono">{{ row.dedup_key }}</span>
          </template>
        </el-table-column>
        <el-table-column label="尝试次数" width="90" align="center">
          <template #default="{ row }">{{ row.attempts ?? 0 }}</template>
        </el-table-column>
        <el-table-column label="标题" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">{{ row.title ?? '-' }}</template>
        </el-table-column>
        <el-table-column label="错误" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.error_message" class="event-error">{{ row.error_message }}</span>
            <span v-else class="vi-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="90" align="center" fixed="right">
          <template #default="{ row }">
            <el-button
              link
              type="primary"
              :disabled="!store.canOperate || row.status !== 'failed'"
              @click.stop="onRetry(asRow<AlertEvent>(row))"
            >
              重试
            </el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无告警事件" />
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

    <el-drawer v-model="drawerVisible" title="告警事件详情" size="640px">
      <template v-if="current">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="ID">
            <span class="vi-mono">#{{ current.id }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="创建时间">
            {{ formatDateTime(current.created_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="告警规则">
            <span class="vi-mono">#{{ current.alert_rule_id }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="通知渠道">
            <span class="vi-mono">#{{ current.channel_id }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="目标">
            <span class="vi-mono">{{ current.target_id ? `#${current.target_id}` : '-' }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="发现项">
            <span class="vi-mono">{{ current.finding_id ? `#${current.finding_id}` : '-' }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="巡检运行">
            <span class="vi-mono">{{ current.run_id ? `#${current.run_id}` : '-' }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="事件类型">
            {{ eventTypeText(current.event_type) }}
          </el-descriptions-item>
          <el-descriptions-item label="级别">
            <SeverityTag :level="current.severity" />
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <StatusTag kind="alert-event" :status="current.status" />
          </el-descriptions-item>
          <el-descriptions-item label="尝试次数">
            {{ current.attempts ?? 0 }}
          </el-descriptions-item>
          <el-descriptions-item label="发送时间">
            {{ formatDateTime(current.sent_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="指纹">
            <span class="vi-mono">{{ current.fingerprint }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="去重键">
            <span class="vi-mono">{{ current.dedup_key }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="标题" :span="2">
            {{ current.title ?? '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="错误信息" :span="2">
            <span v-if="current.error_message" class="event-error">{{ current.error_message }}</span>
            <span v-else class="vi-muted">-</span>
          </el-descriptions-item>
        </el-descriptions>

        <div class="body-title">事件正文</div>
        <pre class="event-body">{{ bodyText || '（无正文）' }}</pre>
      </template>
    </el-drawer>
  </div>
</template>

<style scoped>
.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

.event-error {
  color: #f56c6c;
  word-break: break-all;
}

.body-title {
  margin: 16px 0 6px;
  font-weight: 600;
}

.event-body {
  margin: 0;
  padding: 12px;
  border: 1px solid #e8ebf0;
  border-radius: 6px;
  background: #fafbfd;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 420px;
  overflow: auto;
}

:deep(.el-table__row) {
  cursor: pointer;
}
</style>
