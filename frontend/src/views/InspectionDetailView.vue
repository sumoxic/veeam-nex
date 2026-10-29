<script setup lang="ts">
/**
 * 巡检详情：单次运行的元信息、发现项列表与原始清单。
 *
 * 详情取自 GET /inspections/{id}，发现项取自 /inspections/{id}/findings，
 * 原始清单取自 /inspections/{id}/inventory。
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getInspection, getRunFindings, getRunInventory } from '@/api'
import type { Finding, InspectionRunDetail } from '@/api/types'
import SeverityTag from '@/components/SeverityTag.vue'
import StatusTag from '@/components/StatusTag.vue'
import JsonViewer from '@/components/JsonViewer.vue'
import VersionTag from '@/components/VersionTag.vue'
import { formatDateTime, formatDuration } from '@/utils/format'

const route = useRoute()
const router = useRouter()

const TRIGGER_LABELS: Record<string, string> = {
  manual: '手动',
  schedule: '定时',
  scheduled: '定时',
  api: '接口',
}

const run = ref<InspectionRunDetail | null>(null)
const findings = ref<Finding[]>([])
const inventory = ref<Record<string, unknown>>({})
const loading = ref(false)
const inventoryLoading = ref(false)

const runId = computed(() => Number(route.params.id))

function errorText(err: unknown, fallback: string): string {
  return err instanceof Error ? err.message : fallback
}

function triggerTypeText(value?: string | null): string {
  if (!value) return '-'
  return TRIGGER_LABELS[value] ?? value
}

/** 时钟来源说明：VBR 服务器时钟 vs 平台时钟 */
const clockNote = computed(() => {
  if (!run.value) return ''
  return run.value.clock_source === 'vbr'
    ? '本次巡检以 VBR 服务器时钟为时间基准'
    : '本次巡检以平台时钟为时间基准'
})

async function loadRun() {
  if (!Number.isFinite(runId.value) || runId.value <= 0) {
    ElMessage.error('巡检运行 ID 无效')
    return
  }
  loading.value = true
  try {
    const detail = await getInspection(runId.value)
    run.value = detail
    if (detail.inventory_json) {
      inventory.value = detail.inventory_json
    }
  } catch (err) {
    ElMessage.error(errorText(err, '加载巡检详情失败'))
  } finally {
    loading.value = false
  }
}

async function loadFindings() {
  try {
    const res = await getRunFindings(runId.value)
    findings.value = res.items ?? []
  } catch (err) {
    ElMessage.error(errorText(err, '加载发现项失败'))
  }
}

async function loadInventory() {
  inventoryLoading.value = true
  try {
    const raw = await getRunInventory(runId.value)
    // 后端返回 { inventory: {...} }，同时兼容直接返回清单本体的情况
    const body = raw as { inventory?: Record<string, unknown> }
    inventory.value = body.inventory ?? raw
  } catch (err) {
    ElMessage.error(errorText(err, '加载原始清单失败'))
  } finally {
    inventoryLoading.value = false
  }
}

function goBack() {
  router.push('/inspections')
}

onMounted(async () => {
  await loadRun()
  await Promise.all([loadFindings(), loadInventory()])
})
</script>

<template>
  <div class="vi-page" v-loading="loading">
    <div class="vi-page-header">
      <h2 class="vi-page-title">
        巡检详情
        <span v-if="run" class="vi-mono run-id">#{{ run.id }}</span>
      </h2>
      <div class="vi-toolbar">
        <el-button @click="goBack">返回</el-button>
      </div>
    </div>

    <template v-if="run">
      <div class="vi-card meta-card">
        <div class="meta-grid">
          <div class="meta-item">
            <span class="meta-label">运行 ID</span>
            <span class="vi-mono">#{{ run.id }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">状态</span>
            <StatusTag kind="run" :status="run.status" size="default" />
          </div>
          <div class="meta-item">
            <span class="meta-label">目标</span>
            <span class="vi-mono">#{{ run.target_id }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">触发方式</span>
            <span>{{ triggerTypeText(run.trigger_type) }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">开始时间</span>
            <span>{{ formatDateTime(run.started_at) }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">结束时间</span>
            <span>{{ formatDateTime(run.finished_at) }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">耗时</span>
            <span>{{ formatDuration(run.duration_ms) }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">时钟来源</span>
            <span>
              <span class="vi-mono">{{ run.clock_source }}</span>
              <span class="vi-muted clock-note"> · {{ clockNote }}</span>
            </span>
          </div>
          <div class="meta-item">
            <span class="meta-label">VBR 版本</span>
            <VersionTag :build="run.vbr_build" size="default" />
            <span class="vi-mono vi-muted">{{ run.vbr_build ?? '-' }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">VBR 服务器时间</span>
            <span>{{ formatDateTime(run.vbr_server_time) }}</span>
          </div>
        </div>
      </div>

      <div class="tiles">
        <div class="tile tile-critical">
          <span class="tile-value">{{ run.findings_critical ?? 0 }}</span>
          <span class="tile-label">严重</span>
        </div>
        <div class="tile tile-warn">
          <span class="tile-value">{{ run.findings_warn ?? 0 }}</span>
          <span class="tile-label">警告</span>
        </div>
        <div class="tile tile-info">
          <span class="tile-value">{{ run.findings_info ?? 0 }}</span>
          <span class="tile-label">提示</span>
        </div>
        <div class="tile tile-error">
          <span class="tile-value">{{ run.error_count ?? 0 }}</span>
          <span class="tile-label">错误</span>
        </div>
      </div>

      <el-alert
        v-if="run.error_message"
        type="error"
        show-icon
        :closable="false"
        :title="run.error_message"
        class="error-alert"
      />

      <div class="vi-card">
        <el-tabs>
          <el-tab-pane label="发现项">
            <el-table :data="findings" border stripe style="width: 100%">
              <el-table-column label="级别" width="90" align="center">
                <template #default="{ row }">
                  <SeverityTag :level="row.level" />
                </template>
              </el-table-column>
              <el-table-column prop="rule_key" label="规则" width="180">
                <template #default="{ row }">
                  <span class="vi-mono">{{ row.rule_key }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="category" label="类别" width="140" />
              <el-table-column prop="subject" label="对象" min-width="160" />
              <el-table-column prop="message" label="说明" min-width="240" />
              <el-table-column label="指标" width="110" align="right">
                <template #default="{ row }">
                  {{ row.metric_value ?? '-' }}
                </template>
              </el-table-column>
              <el-table-column label="阈值" width="110" align="right">
                <template #default="{ row }">
                  {{ row.threshold_value ?? '-' }}
                </template>
              </el-table-column>
              <el-table-column label="状态" width="100" align="center">
                <template #default="{ row }">
                  <StatusTag kind="finding" :status="row.status" />
                </template>
              </el-table-column>
              <template #empty>
                <el-empty description="本次巡检没有发现项" />
              </template>
            </el-table>
          </el-tab-pane>

          <el-tab-pane label="原始清单">
            <JsonViewer :data="inventory" />
            <div v-if="inventoryLoading" class="vi-muted">加载中…</div>
          </el-tab-pane>
        </el-tabs>
      </div>
    </template>

    <div v-else-if="!loading" class="vi-card">
      <el-empty description="未找到该巡检记录" />
    </div>
  </div>
</template>

<style scoped>
.run-id {
  font-size: 14px;
  color: var(--vi-text-muted);
  margin-left: 6px;
}

.meta-card {
  margin-bottom: 12px;
}

.meta-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 12px 20px;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.meta-label {
  color: var(--vi-text-muted);
  min-width: 84px;
}

.clock-note {
  font-size: 12px;
}

.tiles {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 12px;
}

.tile {
  background: #fff;
  border-radius: 8px;
  padding: 14px 16px;
  box-shadow: 0 1px 4px rgba(31, 41, 51, 0.06);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.tile-value {
  font-size: 24px;
  font-weight: 600;
}

.tile-label {
  color: var(--vi-text-muted);
  font-size: 13px;
}

.tile-critical .tile-value {
  color: #f56c6c;
}

.tile-warn .tile-value {
  color: #e6a23c;
}

.tile-info .tile-value {
  color: #409eff;
}

.tile-error .tile-value {
  color: #909399;
}

.error-alert {
  margin-bottom: 12px;
}
</style>
