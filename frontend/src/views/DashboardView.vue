<script setup lang="ts">
/**
 * 仪表盘（巡检驾驶舱）：
 * 按巡检轮次回看当时的备份任务、存储库容量、还原点、发现项与基础设施状态。
 */
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { dashboardRun, dashboardRuns, findingsTrend } from '@/api'
import type {
  DashboardRunOption,
  FindingsTrendPoint,
  RunDashboard,
  RunDashboardJob,
  RunDashboardRepository,
  RunDashboardSession,
} from '@/api/types'
import DonutChart from '@/components/charts/DonutChart.vue'
import LineChart from '@/components/charts/LineChart.vue'
import { formatBytes, formatDateTime, formatDuration, formatPercent } from '@/utils/format'
import { versionLabel } from '@/utils/version'

const router = useRouter()

const RUN_STATUS_TEXT: Record<string, string> = {
  success: '成功',
  failed: '失败',
  partial: '部分成功',
  running: '运行中',
}

const TRIGGER_TEXT: Record<string, string> = {
  manual: '手动',
  schedule: '计划任务',
  api: 'API',
}

const LEVEL_TEXT: Record<string, string> = {
  critical: '严重',
  warn: '警告',
  info: '提示',
}

const loading = ref(false)
const detailLoading = ref(false)
const runs = ref<DashboardRunOption[]>([])
const selectedRunId = ref<number | null>(null)
const detail = ref<RunDashboard | null>(null)
const trendItems = ref<FindingsTrendPoint[]>([])

function errorMessage(err: unknown, fallback: string): string {
  if (err instanceof Error && err.message) return err.message
  return fallback
}

function runStatusText(status?: string | null): string {
  if (!status) return '-'
  return RUN_STATUS_TEXT[status] ?? status
}

function triggerText(value?: string | null): string {
  if (!value) return '-'
  return TRIGGER_TEXT[value] ?? value
}

function runOptionLabel(run: DashboardRunOption): string {
  return `${formatDateTime(run.started_at)} · ${run.target_name} · ${versionLabel(run.vbr_build)} · ${runStatusText(run.status)}`
}

function resultText(value?: string | null): string {
  const key = (value ?? '').toLowerCase()
  if (key === 'success') return '成功'
  if (key === 'warning') return '警告'
  if (key === 'failed') return '失败'
  return value || '未知'
}

function resultTone(value?: string | null): string {
  const key = (value ?? '').toLowerCase()
  if (key === 'success') return 'ok'
  if (key === 'warning') return 'warn'
  if (key === 'failed') return 'fail'
  return 'neutral'
}

function nextRunText(job: RunDashboardJob): string {
  if (job.next_run) return formatDateTime(job.next_run)
  if (!job.next_run_policy || job.next_run_policy === '<Not scheduled>') return '未计划'
  return job.next_run_policy
}

function formatGb(value?: number | null): string {
  if (value === null || value === undefined) return '-'
  if (value >= 1024) return `${(value / 1024).toFixed(2)} TB`
  return `${Number(value).toFixed(1)} GB`
}

function formatAge(hours?: number | null): string {
  if (hours === null || hours === undefined) return '-'
  if (hours < 24) return `${hours.toFixed(1)} 小时`
  return `${(hours / 24).toFixed(1)} 天`
}

function formatDateOnly(value?: string | null): string {
  if (!value) return '-'
  return formatDateTime(value).slice(0, 10)
}

// ------------------------------------------------------------------ 数据加载

async function loadRuns(keepSelection = false) {
  const result = await dashboardRuns(60)
  runs.value = result.items ?? []
  if (keepSelection && selectedRunId.value && runs.value.some((r) => r.id === selectedRunId.value)) {
    return
  }
  const preferred =
    runs.value.find((r) => r.status === 'success') ??
    runs.value.find((r) => r.status !== 'running') ??
    runs.value[0]
  selectedRunId.value = preferred ? preferred.id : null
}

async function loadRun(runId: number) {
  detailLoading.value = true
  try {
    detail.value = await dashboardRun(runId)
  } catch (err) {
    ElMessage.error(errorMessage(err, '加载巡检数据失败'))
  } finally {
    detailLoading.value = false
  }
}

async function loadTrend() {
  try {
    const trend = await findingsTrend({ days: 30 })
    trendItems.value = trend.items ?? []
  } catch {
    trendItems.value = []
  }
}

async function onRunChange(value: number) {
  await loadRun(value)
}

async function bootstrap() {
  loading.value = true
  try {
    await loadRuns()
    if (selectedRunId.value) await loadRun(selectedRunId.value)
    await loadTrend()
  } catch (err) {
    ElMessage.error(errorMessage(err, '加载仪表盘失败'))
  } finally {
    loading.value = false
  }
}

async function refresh() {
  loading.value = true
  try {
    await loadRuns(true)
    if (selectedRunId.value) await loadRun(selectedRunId.value)
    await loadTrend()
  } catch (err) {
    ElMessage.error(errorMessage(err, '刷新失败'))
  } finally {
    loading.value = false
  }
}

onMounted(bootstrap)

// ------------------------------------------------------------------ 派生数据

const run = computed(() => detail.value?.run ?? null)
const target = computed(() => detail.value?.target ?? null)
const jobStats = computed(() =>
  detail.value?.job_stats ?? {
    total: 0,
    success: 0,
    warning: 0,
    failed: 0,
    running: 0,
    disabled: 0,
    unknown: 0,
  },
)
const repoStats = computed(() =>
  detail.value?.repo_stats ?? {
    total: 0,
    online: 0,
    capacity_gb: 0,
    free_gb: 0,
    used_gb: 0,
    free_percent: null,
  },
)
const restorePoints = computed(
  () =>
    detail.value?.restore_points ?? {
      total: 0,
      avg_age_hours: null,
      max_age_hours: null,
      clean: 0,
      warning: 0,
      unknown: 0,
      items: [],
    },
)
const objects = computed(() =>
  detail.value?.backup_objects ?? { total: 0, total_size: 0, failed: 0, items: [] },
)
const findings = computed(() => detail.value?.findings ?? [])
const findingCount = computed(() => {
  const by = detail.value?.findings_by_level
  if (!by) return 0
  return (by.critical ?? 0) + (by.warn ?? 0) + (by.info ?? 0)
})

const runTone = computed(() => {
  const status = run.value?.status
  if (status === 'success') return 'ok'
  if (status === 'failed') return 'fail'
  if (status === 'partial') return 'warn'
  return 'neutral'
})

const jobDonutItems = computed(() => [
  { name: '成功', value: jobStats.value.success, color: '#3f8f5c' },
  { name: '警告', value: jobStats.value.warning, color: '#d98a2b' },
  { name: '失败', value: jobStats.value.failed, color: '#d94f4e' },
  { name: '未知', value: jobStats.value.unknown, color: '#c3c7ce' },
])

const usedPercent = computed(() => {
  const free = repoStats.value.free_percent
  if (free === null || free === undefined) return 0
  return Math.max(0, Math.min(100, 100 - free))
})

const license = computed(() => detail.value?.license ?? null)
const licenseArc = computed(() => {
  const value = license.value?.used_percent ?? 0
  // 用量极低时保留一小段可见弧，避免整圈看起来像没有数据
  return Math.max(Math.min(value, 100), value > 0 ? 1.5 : 0)
})

const ringStyle = computed(() => ({ '--p': `${licenseArc.value}%` }))

const trendLabels = computed(() => trendItems.value.map((item) => String(item.time).slice(5)))
const trendSeries = computed(() => [
  {
    name: '严重',
    data: trendItems.value.map((item) => item.critical ?? 0),
  },
  {
    name: '警告',
    data: trendItems.value.map((item) => item.warn ?? 0),
  },
  {
    name: '提示',
    data: trendItems.value.map((item) => item.info ?? 0),
  },
])

function repoUsedPercent(repo: RunDashboardRepository): number {
  const free = repo.free_percent
  if (free === null || free === undefined) return 0
  return Math.max(0, Math.min(100, 100 - free))
}

function repoBarTone(percent: number): string {
  if (percent >= 85) return 'danger'
  if (percent >= 70) return 'warn'
  return 'ok'
}

function sessionTone(session: RunDashboardSession): string {
  return resultTone(session.result)
}

function openFindings() {
  router.push('/findings')
}
</script>

<template>
  <div class="vi-page dash-page">
    <header class="dash-head">
      <div class="dash-head-text">
        <div class="vi-eyebrow">
          <span class="pulse-dot" />
          INSPECTION CONSOLE
        </div>
        <h1 class="dash-title">巡检驾驶舱</h1>
        <p class="dash-sub">
          <template v-if="target">
            {{ target.name }} · {{ target.host }}
            <span class="sep">/</span>
            {{ formatDateTime(run?.started_at) }} 的巡检快照
          </template>
          <template v-else>选择一次巡检，回看当时的基础设施状态</template>
        </p>
      </div>
      <div class="dash-controls">
        <el-select
          v-model="selectedRunId"
          class="run-select"
          filterable
          placeholder="选择巡检时间"
          :disabled="runs.length === 0"
          @change="onRunChange"
        >
          <el-option
            v-for="item in runs"
            :key="item.id"
            :value="item.id"
            :label="runOptionLabel(item)"
          >
            <div class="run-option">
              <span class="run-option-time">{{ formatDateTime(item.started_at) }}</span>
              <span class="run-option-meta">
                {{ item.target_name }} · {{ versionLabel(item.vbr_build) }} ·
                {{ runStatusText(item.status) }}
              </span>
            </div>
          </el-option>
        </el-select>
        <el-button class="ghost-btn" :loading="loading || detailLoading" @click="refresh">
          <el-icon><Refresh /></el-icon>
          <span>刷新</span>
        </el-button>
      </div>
    </header>

    <div v-if="run" class="run-chips">
      <span class="vi-chip" :class="`tone-${runTone}`">
        <i class="vi-dot" />
        {{ runStatusText(run.status) }}
      </span>
      <span class="vi-chip">{{ triggerText(run.trigger_type) }}巡检</span>
      <span class="vi-chip">耗时 {{ formatDuration(run.duration_ms) }}</span>
      <span class="vi-chip">
        {{ versionLabel(run.vbr_build) }}
        <template v-if="run.vbr_build"> · {{ run.vbr_build }}</template>
      </span>
      <span class="vi-chip">时钟基准 · {{ run.clock_source === 'vbr' ? 'VBR 服务器' : '平台' }}</span>
      <span v-if="run.error_count > 0" class="vi-chip tone-warn">
        采集异常 {{ run.error_count }} 项
      </span>
      <el-button
        class="chip-link"
        text
        @click="router.push(`/inspections/${run.id}`)"
      >
        查看该轮巡检详情 →
      </el-button>
    </div>

    <div v-loading="loading || detailLoading" class="dash-body">
      <template v-if="detail">
        <!-- KPI -->
        <section class="kpi-grid">
          <article class="kpi-card reveal" style="--d: 0.02s">
            <div class="kpi-top">
              <span class="kpi-icon blue"><el-icon><Coin /></el-icon></span>
              <span class="kpi-label">备份任务</span>
            </div>
            <div class="kpi-value">{{ jobStats.total }}</div>
            <div class="kpi-foot">
              <span class="legend ok">成功 {{ jobStats.success }}</span>
              <span class="legend warn">警告 {{ jobStats.warning }}</span>
              <span class="legend fail">失败 {{ jobStats.failed }}</span>
            </div>
          </article>

          <article class="kpi-card reveal" style="--d: 0.06s">
            <div class="kpi-top">
              <span class="kpi-icon green"><el-icon><FolderOpened /></el-icon></span>
              <span class="kpi-label">存储库可用空间</span>
            </div>
            <div class="kpi-value">{{ formatGb(repoStats.free_gb) }}</div>
            <div class="kpi-track">
              <div class="kpi-track-fill" :style="{ width: `${usedPercent}%` }" />
            </div>
            <div class="kpi-foot">
              <span>总容量 {{ formatGb(repoStats.capacity_gb) }}</span>
              <span class="vi-muted">已用 {{ formatPercent(usedPercent) }}</span>
            </div>
          </article>

          <article class="kpi-card reveal" style="--d: 0.1s">
            <div class="kpi-top">
              <span class="kpi-icon violet"><el-icon><Collection /></el-icon></span>
              <span class="kpi-label">受保护对象</span>
            </div>
            <div class="kpi-value">{{ objects.total }}</div>
            <div class="kpi-foot">
              <span>数据量 {{ formatBytes(objects.total_size) }}</span>
              <span class="vi-muted">还原点 {{ restorePoints.total }}</span>
            </div>
          </article>

          <article class="kpi-card reveal" style="--d: 0.14s">
            <div class="kpi-top">
              <span class="kpi-icon cyan"><el-icon><Timer /></el-icon></span>
              <span class="kpi-label">还原点平均时效</span>
            </div>
            <div class="kpi-value">{{ formatAge(restorePoints.avg_age_hours) }}</div>
            <div class="kpi-foot">
              <span>最旧 {{ formatAge(restorePoints.max_age_hours) }}</span>
              <span class="vi-muted">恶意软件扫描 {{ restorePoints.clean }} 正常</span>
            </div>
          </article>

          <article class="kpi-card reveal" style="--d: 0.18s">
            <div class="kpi-top">
              <span class="kpi-icon red"><el-icon><Warning /></el-icon></span>
              <span class="kpi-label">本轮发现项</span>
            </div>
            <div class="kpi-value">{{ findingCount }}</div>
            <div class="kpi-foot">
              <span class="legend fail">严重 {{ detail.findings_by_level.critical }}</span>
              <span class="legend warn">警告 {{ detail.findings_by_level.warn }}</span>
              <span class="legend info">提示 {{ detail.findings_by_level.info }}</span>
            </div>
          </article>
        </section>

        <section class="dash-grid">
          <!-- 备份任务 -->
          <article class="panel span-7 reveal" style="--d: 0.22s">
            <div class="panel-head">
              <div>
                <div class="panel-title">备份任务</div>
                <div class="panel-sub">该轮巡检采集到的作业与最近一次运行结果</div>
              </div>
              <span class="vi-chip tiny">{{ jobStats.total }} 个任务</span>
            </div>

            <div class="jobs-layout">
              <div class="jobs-chart">
                <DonutChart
                  :items="jobDonutItems"
                  :center-value="jobStats.success"
                  center-label="运行成功"
                  height="170px"
                />
                <div class="jobs-legend">
                  <span class="legend ok">成功 {{ jobStats.success }}</span>
                  <span class="legend warn">警告 {{ jobStats.warning }}</span>
                  <span class="legend fail">失败 {{ jobStats.failed }}</span>
                  <span v-if="jobStats.disabled > 0" class="legend muted">
                    已禁用 {{ jobStats.disabled }}
                  </span>
                </div>
              </div>

              <div class="jobs-list">
                <div v-for="(job, idx) in detail.jobs" :key="job.id || `job-${idx}`" class="job-row">
                  <span class="job-mark" :class="resultTone(job.last_result)">
                    <el-icon><VideoPlay /></el-icon>
                  </span>
                  <div class="job-main">
                    <div class="job-name">
                      {{ job.name || '-' }}
                      <span v-if="job.is_disabled" class="mini-tag">已禁用</span>
                    </div>
                    <div class="job-meta">
                      {{ job.workload || job.type || '未知负载' }}
                      <template v-if="job.repository_name">· {{ job.repository_name }}</template>
                      <template v-if="job.objects_count !== null && job.objects_count !== undefined">
                        · {{ job.objects_count }} 个对象
                      </template>
                    </div>
                  </div>
                  <div class="job-time">
                    <span>上次 {{ formatDateTime(job.last_run_at) }}</span>
                    <span class="vi-muted">下次 {{ nextRunText(job) }}</span>
                  </div>
                  <span class="result-pill" :class="resultTone(job.last_result)">
                    {{ resultText(job.last_result) }}
                  </span>
                </div>
                <el-empty v-if="detail.jobs.length === 0" description="该轮巡检未采集到备份任务" :image-size="64" />
              </div>
            </div>
          </article>

          <!-- 存储库 -->
          <article class="panel span-5 reveal" style="--d: 0.26s">
            <div class="panel-head">
              <div>
                <div class="panel-title">备份存储库</div>
                <div class="panel-sub">容量与在线状态</div>
              </div>
              <span class="vi-chip tiny">{{ repoStats.online }}/{{ repoStats.total }} 在线</span>
            </div>

            <div class="repo-list">
              <div v-for="(repo, idx) in detail.repositories" :key="repo.id || `repo-${idx}`" class="repo-card">
                <div class="repo-top">
                  <div>
                    <div class="repo-name">
                      {{ repo.name || '-' }}
                      <i
                        class="vi-dot"
                        :class="repo.is_online ? 'is-online' : 'is-offline'"
                      />
                    </div>
                    <div class="repo-path">{{ repo.path || repo.type || '-' }}</div>
                  </div>
                  <span class="repo-percent">{{ formatPercent(repo.free_percent) }} 可用</span>
                </div>
                <div class="repo-track">
                  <div
                    class="repo-fill"
                    :class="repoBarTone(repoUsedPercent(repo))"
                    :style="{ width: `${repoUsedPercent(repo)}%` }"
                  />
                </div>
                <div class="repo-foot">
                  <span>{{ formatGb(repo.free_gb) }} 空闲</span>
                  <span class="vi-muted">共 {{ formatGb(repo.capacity_gb) }}</span>
                </div>
              </div>
              <el-empty v-if="detail.repositories.length === 0" description="该轮巡检未采集到存储库" :image-size="64" />
            </div>
          </article>

          <!-- 受保护对象 -->
          <article class="panel span-7 reveal" style="--d: 0.3s">
            <div class="panel-head">
              <div>
                <div class="panel-title">受保护对象</div>
                <div class="panel-sub">按数据量排序的备份对象</div>
              </div>
              <span class="vi-chip tiny">{{ formatBytes(objects.total_size) }}</span>
            </div>
            <div class="object-list">
              <div v-for="(obj, idx) in detail.backup_objects.items.slice(0, 6)" :key="obj.id || `obj-${idx}`" class="object-row">
                <span class="object-icon"><el-icon><Files /></el-icon></span>
                <div class="object-main">
                  <div class="object-name">{{ obj.name || '-' }}</div>
                  <div class="object-path">{{ obj.path || obj.type || '-' }}</div>
                </div>
                <div class="object-side">
                  <span class="object-size">{{ formatBytes(obj.size) }}</span>
                  <span class="vi-muted">{{ obj.restore_points_count ?? 0 }} 个还原点</span>
                </div>
                <span v-if="obj.last_run_failed" class="result-pill fail">失败</span>
                <span v-else class="result-pill ok">正常</span>
              </div>
              <el-empty v-if="objects.total === 0" description="该轮巡检未采集到受保护对象" :image-size="64" />
            </div>
          </article>

          <!-- 发现项 -->
          <article class="panel span-5 reveal" style="--d: 0.34s">
            <div class="panel-head">
              <div>
                <div class="panel-title">本轮发现项</div>
                <div class="panel-sub">按严重程度排序</div>
              </div>
              <el-button text class="chip-link" @click="openFindings">全部 →</el-button>
            </div>
            <div class="finding-list">
              <div v-for="item in findings.slice(0, 6)" :key="item.id" class="finding-row">
                <span class="sev-dot" :class="item.level" />
                <div class="finding-main">
                  <div class="finding-msg">{{ item.message }}</div>
                  <div class="finding-sub">{{ item.subject }}</div>
                </div>
                <span class="sev-text" :class="item.level">{{ LEVEL_TEXT[item.level] ?? item.level }}</span>
              </div>
              <el-empty v-if="findings.length === 0" description="本轮没有发现项，状态良好" :image-size="64" />
            </div>
          </article>

          <!-- 基础设施 -->
          <article class="panel span-7 reveal" style="--d: 0.38s">
            <div class="panel-head">
              <div>
                <div class="panel-title">基础设施与许可</div>
                <div class="panel-sub">代理、受管服务器与许可实例</div>
              </div>
              <span class="vi-chip tiny">{{ detail.server.name || '-' }}</span>
            </div>

            <div class="infra-layout">
              <div class="license-block">
                <div class="ring" :style="ringStyle">
                  <div class="ring-inner">
                    <strong>{{ formatPercent(license?.used_percent, 2) }}</strong>
                    <span>实例用量</span>
                  </div>
                </div>
                <div class="license-info">
                  <div class="license-edition">{{ license?.edition || '-' }}</div>
                  <div class="license-meta">
                    {{ license?.used_instances ?? '-' }} / {{ license?.licensed_instances ?? '-' }} 实例
                    <template v-if="license?.type"> · {{ license.type }}</template>
                  </div>
                  <div class="license-meta">到期 {{ formatDateOnly(license?.expiration_date) }}</div>
                  <span class="vi-chip tiny" :class="license?.status === 'Valid' ? 'tone-ok' : 'tone-warn'">
                    {{ license?.status || '未知' }}
                  </span>
                </div>
              </div>

              <div class="infra-lists">
                <div class="infra-group">
                  <div class="infra-label">代理</div>
                  <div v-for="(proxy, idx) in detail.proxies" :key="proxy.id || `proxy-${idx}`" class="infra-row">
                    <span class="status-dot" :class="proxy.is_online && !proxy.is_disabled ? 'ok' : 'off'" />
                    <span class="infra-name">{{ proxy.name }}</span>
                    <span class="infra-meta">{{ proxy.host_name || proxy.type }}</span>
                  </div>
                  <div v-if="detail.proxies.length === 0" class="infra-empty">未采集到代理</div>
                </div>

                <div class="infra-group">
                  <div class="infra-label">受管服务器</div>
                  <div
                    v-for="(server, idx) in detail.managed_servers"
                    :key="server.id || `server-${idx}`"
                    class="infra-row"
                  >
                    <span
                      class="status-dot"
                      :class="server.status === 'Available' ? 'ok' : 'off'"
                    />
                    <span class="infra-name">{{ server.name }}</span>
                    <span class="infra-meta">{{ server.vi_host_type || server.type }}</span>
                  </div>
                  <div v-if="detail.managed_servers.length === 0" class="infra-empty">未采集到服务器</div>
                </div>
              </div>
            </div>
          </article>

          <!-- 最近会话 -->
          <article class="panel span-5 reveal" style="--d: 0.42s">
            <div class="panel-head">
              <div>
                <div class="panel-title">最近会话</div>
                <div class="panel-sub">VBR 会话中心最新记录</div>
              </div>
            </div>
            <div class="session-list">
              <div v-for="(session, idx) in detail.sessions.slice(0, 8)" :key="session.id || `session-${idx}`" class="session-row">
                <span class="status-dot" :class="sessionTone(session)" />
                <div class="session-main">
                  <div class="session-name">{{ session.name }}</div>
                  <div class="session-meta">{{ session.session_type || '-' }}</div>
                </div>
                <span class="session-time">{{ formatDateTime(session.end_time || session.creation_time) }}</span>
              </div>
              <el-empty v-if="detail.sessions.length === 0" description="该轮巡检未采集到会话" :image-size="64" />
            </div>
          </article>

          <!-- 趋势 -->
          <article class="panel span-12 reveal" style="--d: 0.46s">
            <div class="panel-head">
              <div>
                <div class="panel-title">近 30 天发现项趋势</div>
                <div class="panel-sub">按严重程度统计的出现数量</div>
              </div>
            </div>
            <LineChart
              v-if="trendItems.length > 0"
              :labels="trendLabels"
              :series="trendSeries"
              height="240px"
            />
            <el-empty v-else description="暂无趋势数据" :image-size="64" />
          </article>
        </section>
      </template>

      <div v-else-if="!loading" class="empty-state panel">
        <div class="empty-orbit" />
        <h3>还没有巡检记录</h3>
        <p class="vi-muted">先到「巡检目标」发起一次巡检，仪表盘就会展示当时的完整快照。</p>
        <el-button class="primary-btn" @click="router.push('/targets')">前往巡检目标</el-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dash-page {
  max-width: 1440px;
  margin: 0 auto;
}

/* ---------------- 页头 ---------------- */

.dash-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}

.vi-eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.16em;
  color: var(--vi-muted);
  margin-bottom: 10px;
}

.pulse-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--vi-accent);
  box-shadow: 0 0 0 4px rgba(77, 107, 254, 0.14);
  animation: pulse 2.4s ease-in-out infinite;
}

@keyframes pulse {
  0%,
  100% {
    box-shadow: 0 0 0 3px rgba(77, 107, 254, 0.12);
  }
  50% {
    box-shadow: 0 0 0 7px rgba(77, 107, 254, 0.04);
  }
}

.dash-title {
  margin: 0;
  font-size: clamp(26px, 3vw, 34px);
  font-weight: 650;
  letter-spacing: -0.035em;
  line-height: 1.1;
  color: var(--vi-heading);
}

.dash-sub {
  margin: 8px 0 0;
  font-size: 13px;
  color: var(--vi-text-2);
}

.sep {
  margin: 0 8px;
  color: var(--vi-muted);
}

.dash-controls {
  display: flex;
  align-items: center;
  gap: 10px;
}

.run-select {
  width: 320px;
}

.run-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.run-option-time {
  font-variant-numeric: tabular-nums;
}

.run-option-meta {
  font-size: 12px;
  color: var(--vi-muted);
}

.run-chips {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin: 4px 0 18px;
}

.chip-link {
  color: var(--vi-accent);
  font-size: 12px;
}

/* ---------------- KPI ---------------- */

.dash-body {
  min-height: 320px;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 14px;
}

.kpi-card {
  position: relative;
  padding: 18px 18px 16px;
  border-radius: var(--vi-radius-lg);
  background:
    radial-gradient(120% 120% at 100% 0%, rgba(77, 107, 254, 0.06), transparent 55%),
    var(--vi-surface);
  border: 1px solid var(--vi-hairline);
  box-shadow: var(--vi-shadow-sm);
  transition: transform 0.35s cubic-bezier(0.22, 1, 0.36, 1), box-shadow 0.35s;
}

.kpi-card:hover {
  transform: translateY(-3px);
  box-shadow: var(--vi-shadow-lift);
}

.kpi-top {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.kpi-icon {
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  border-radius: 10px;
  font-size: 15px;
}

.kpi-icon.blue {
  background: #eef1ff;
  color: #4d6bfe;
}

.kpi-icon.green {
  background: #e9f5ee;
  color: #3f8f5c;
}

.kpi-icon.violet {
  background: #f0edfd;
  color: #7c6cf0;
}

.kpi-icon.cyan {
  background: #e6f6f8;
  color: #3d98a5;
}

.kpi-icon.red {
  background: #fdecec;
  color: #d94f4e;
}

.kpi-label {
  font-size: 12px;
  color: var(--vi-muted);
  letter-spacing: 0.02em;
}

.kpi-value {
  font-size: 30px;
  font-weight: 650;
  letter-spacing: -0.035em;
  line-height: 1.1;
  color: var(--vi-heading);
  font-variant-numeric: tabular-nums;
}

.kpi-foot {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 10px;
  font-size: 12px;
  color: var(--vi-text-2);
}

.kpi-track {
  height: 4px;
  border-radius: 999px;
  background: #efeeeb;
  margin-top: 12px;
  overflow: hidden;
}

.kpi-track-fill {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #6f8bff, #4d6bfe);
}

.legend {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.legend::before {
  content: '';
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

.legend.ok {
  color: #3f8f5c;
}

.legend.warn {
  color: #b7791f;
}

.legend.fail {
  color: #d94f4e;
}

.legend.info {
  color: #6b7280;
}

.legend.muted {
  color: var(--vi-muted);
}

/* ---------------- 面板 ---------------- */

.dash-grid {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: 14px;
}

.panel {
  padding: 20px;
  border-radius: var(--vi-radius-lg);
  background: var(--vi-surface);
  border: 1px solid var(--vi-hairline);
  box-shadow: var(--vi-shadow-sm);
}

.span-5 {
  grid-column: span 5;
}

.span-7 {
  grid-column: span 7;
}

.span-12 {
  grid-column: span 12;
}

.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.panel-title {
  font-size: 15px;
  font-weight: 600;
  letter-spacing: -0.01em;
  color: var(--vi-heading);
}

.panel-sub {
  margin-top: 3px;
  font-size: 12px;
  color: var(--vi-muted);
}

/* ---------------- 任务 ---------------- */

.jobs-layout {
  display: grid;
  grid-template-columns: 200px minmax(0, 1fr);
  gap: 20px;
  align-items: start;
}

.jobs-legend {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 12px;
  margin-top: 4px;
}

.jobs-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.job-row {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 14px;
  background: var(--vi-surface-2);
  border: 1px solid transparent;
  transition: background 0.25s, border-color 0.25s, transform 0.25s;
}

.job-row:hover {
  background: #fff;
  border-color: var(--vi-border);
  transform: translateX(2px);
}

.job-mark {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  font-size: 15px;
  background: #eef1ff;
  color: #4d6bfe;
}

.job-mark.ok {
  background: #e9f5ee;
  color: #3f8f5c;
}

.job-mark.warn {
  background: #fdf3e2;
  color: #b7791f;
}

.job-mark.fail {
  background: #fdecec;
  color: #d94f4e;
}

.job-name {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--vi-heading);
}

.job-meta {
  margin-top: 3px;
  font-size: 12px;
  color: var(--vi-muted);
}

.job-time {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 3px;
  font-size: 11px;
  color: var(--vi-text-2);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.mini-tag {
  padding: 1px 7px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 500;
  color: var(--vi-muted);
  background: #eceae6;
}

.result-pill {
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.result-pill.ok {
  color: #2f7a4c;
  background: #e9f5ee;
}

.result-pill.warn {
  color: #a06a15;
  background: #fdf3e2;
}

.result-pill.fail {
  color: #c23b3a;
  background: #fdecec;
}

.result-pill.neutral {
  color: var(--vi-muted);
  background: #f0efec;
}

/* ---------------- 存储库 ---------------- */

.repo-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.repo-card {
  padding: 14px;
  border-radius: 16px;
  background: var(--vi-surface-2);
  border: 1px solid transparent;
  transition: border-color 0.25s, background 0.25s;
}

.repo-card:hover {
  background: #fff;
  border-color: var(--vi-border);
}

.repo-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.repo-name {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 13px;
  font-weight: 600;
  color: var(--vi-heading);
}

.repo-path {
  margin-top: 3px;
  font-size: 11px;
  color: var(--vi-muted);
  font-family: var(--vi-font-mono);
  word-break: break-all;
}

.repo-percent {
  font-size: 11px;
  color: var(--vi-muted);
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.repo-track {
  height: 6px;
  border-radius: 999px;
  background: #eceae6;
  overflow: hidden;
}

.repo-fill {
  height: 100%;
  border-radius: inherit;
  transition: width 0.8s cubic-bezier(0.22, 1, 0.36, 1);
  background: linear-gradient(90deg, #7fb08e, #3f8f5c);
}

.repo-fill.warn {
  background: linear-gradient(90deg, #e8b767, #c58a2a);
}

.repo-fill.danger {
  background: linear-gradient(90deg, #e88484, #d94f4e);
}

.repo-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
  font-size: 11px;
  color: var(--vi-text-2);
}

/* ---------------- 对象 ---------------- */

.object-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.object-row {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 12px;
  padding: 9px 10px;
  border-radius: 12px;
  transition: background 0.25s;
}

.object-row:hover {
  background: var(--vi-surface-2);
}

.object-icon {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  background: #f0edfd;
  color: #7c6cf0;
}

.object-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--vi-heading);
}

.object-path {
  margin-top: 2px;
  font-size: 11px;
  color: var(--vi-muted);
  font-family: var(--vi-font-mono);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.object-side {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
  font-size: 11px;
  color: var(--vi-text-2);
  font-variant-numeric: tabular-nums;
}

.object-size {
  font-weight: 600;
  color: var(--vi-heading);
}

/* ---------------- 发现项 ---------------- */

.finding-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.finding-row {
  display: grid;
  grid-template-columns: 8px minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  padding: 10px 8px;
  border-radius: 12px;
  transition: background 0.25s;
}

.finding-row:hover {
  background: var(--vi-surface-2);
}

.sev-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #9aa0a6;
}

.sev-dot.critical {
  background: #d94f4e;
  box-shadow: 0 0 0 4px rgba(217, 79, 78, 0.12);
}

.sev-dot.warn {
  background: #d98a2b;
  box-shadow: 0 0 0 4px rgba(217, 138, 43, 0.12);
}

.sev-dot.info {
  background: #7f8792;
}

.finding-msg {
  font-size: 13px;
  color: var(--vi-heading);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.finding-sub {
  margin-top: 2px;
  font-size: 11px;
  color: var(--vi-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sev-text {
  font-size: 11px;
  font-weight: 600;
  color: var(--vi-muted);
}

.sev-text.critical {
  color: #d94f4e;
}

.sev-text.warn {
  color: #b7791f;
}

/* ---------------- 基础设施 ---------------- */

.infra-layout {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 24px;
  align-items: center;
}

.license-block {
  display: flex;
  align-items: center;
  gap: 16px;
}

.ring {
  width: 96px;
  height: 96px;
  border-radius: 50%;
  background: conic-gradient(#1a1615 var(--p, 0%), #efeeeb 0);
  display: grid;
  place-items: center;
  flex: none;
}

.ring-inner {
  width: 78px;
  height: 78px;
  border-radius: 50%;
  background: var(--vi-surface);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
}

.ring-inner strong {
  font-size: 16px;
  font-weight: 650;
  letter-spacing: -0.02em;
  color: var(--vi-heading);
}

.ring-inner span {
  font-size: 10px;
  color: var(--vi-muted);
}

.license-edition {
  font-size: 14px;
  font-weight: 600;
  color: var(--vi-heading);
}

.license-meta {
  margin-top: 4px;
  font-size: 12px;
  color: var(--vi-muted);
}

.license-info .vi-chip {
  margin-top: 8px;
}

.infra-lists {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.infra-label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--vi-muted);
  text-transform: uppercase;
  margin-bottom: 8px;
}

.infra-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 0;
  font-size: 12px;
}

.infra-name {
  color: var(--vi-heading);
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.infra-meta {
  margin-left: auto;
  color: var(--vi-muted);
  font-size: 11px;
  white-space: nowrap;
}

.infra-empty {
  font-size: 12px;
  color: var(--vi-muted);
  padding: 4px 0;
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #c3c7ce;
  flex: none;
}

.status-dot.ok {
  background: #3fbf7f;
  box-shadow: 0 0 0 3px rgba(63, 191, 127, 0.12);
}

.status-dot.warn {
  background: #d98a2b;
  box-shadow: 0 0 0 3px rgba(217, 138, 43, 0.12);
}

.status-dot.off {
  background: #c3c7ce;
}

.status-dot.fail {
  background: #d94f4e;
  box-shadow: 0 0 0 3px rgba(217, 79, 78, 0.12);
}

/* ---------------- 会话 ---------------- */

.session-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.session-row {
  display: grid;
  grid-template-columns: 8px minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  padding: 8px;
  border-radius: 10px;
  transition: background 0.25s;
}

.session-row:hover {
  background: var(--vi-surface-2);
}

.session-name {
  font-size: 12.5px;
  color: var(--vi-heading);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-meta {
  margin-top: 2px;
  font-size: 10.5px;
  color: var(--vi-muted);
}

.session-time {
  font-size: 10.5px;
  color: var(--vi-muted);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

/* ---------------- 空状态 ---------------- */

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 64px 24px;
  text-align: center;
}

.empty-state h3 {
  margin: 0;
  font-size: 18px;
  letter-spacing: -0.02em;
}

.empty-state p {
  margin: 0 0 8px;
}

.empty-orbit {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background:
    radial-gradient(circle at 50% 50%, #fff 38%, transparent 40%),
    conic-gradient(from 0deg, #4d6bfe, #79bd89, #f2af63, #4d6bfe);
  animation: spin 8s linear infinite;
  opacity: 0.85;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* ---------------- 响应式 ---------------- */

@media (max-width: 1280px) {
  .kpi-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 1080px) {
  .span-5,
  .span-7 {
    grid-column: span 12;
  }

  .jobs-layout {
    grid-template-columns: 180px minmax(0, 1fr);
  }
}

@media (max-width: 760px) {
  .kpi-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .dash-controls {
    width: 100%;
  }

  .run-select {
    flex: 1;
    width: auto;
  }

  .jobs-layout,
  .infra-layout {
    grid-template-columns: 1fr;
  }

  .jobs-chart {
    max-width: 220px;
    margin: 0 auto;
  }

  .infra-lists {
    grid-template-columns: 1fr;
  }

  .object-path {
    max-width: 180px;
  }
}
</style>
