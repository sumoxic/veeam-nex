<script setup lang="ts">
/**
 * 巡检记录：巡检运行历史列表 + 手动触发巡检。
 *
 * 列表数据来自 GET /inspections（分页），目标下拉来自 GET /targets。
 * 触发巡检由后端异步执行（先建运行记录再后台采集），所以成功后刷新列表即可。
 */
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { listInspections, listTargets, triggerInspection } from '@/api'
import type { InspectionRun, Target } from '@/api/types'
import StatusTag from '@/components/StatusTag.vue'
import { formatDateTime, formatDuration } from '@/utils/format'
import { asRow } from '@/utils/table'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const store = useUserStore()

/** 状态筛选项；空字符串表示不限 */
const STATUS_OPTIONS = [
  { label: '全部状态', value: '' },
  { label: '运行中', value: 'running' },
  { label: '成功', value: 'success' },
  { label: '失败', value: 'failed' },
  { label: '部分成功', value: 'partial' },
]

const TRIGGER_LABELS: Record<string, string> = {
  manual: '手动',
  schedule: '定时',
  scheduled: '定时',
  api: '接口',
}

const targets = ref<Target[]>([])
const rows = ref<InspectionRun[]>([])
const total = ref(0)
const loading = ref(false)

const filters = reactive({
  target_id: '' as number | '',
  status: '' as string,
})
const page = ref(1)
const size = ref(20)

// ---- 立即巡检对话框 ----
const triggerVisible = ref(false)
const triggerTargetId = ref<number | ''>('')
const triggering = ref(false)

function errorText(err: unknown, fallback: string): string {
  return err instanceof Error ? err.message : fallback
}

function triggerTypeText(value?: string | null): string {
  if (!value) return '-'
  return TRIGGER_LABELS[value] ?? value
}

async function loadTargets() {
  try {
    const res = await listTargets()
    targets.value = res.items ?? []
  } catch (err) {
    ElMessage.error(errorText(err, '加载目标列表失败'))
  }
}

async function load() {
  loading.value = true
  try {
    const params: { target_id?: number; status?: string; page: number; size: number } = {
      page: page.value,
      size: size.value,
    }
    if (filters.target_id !== '') params.target_id = filters.target_id
    if (filters.status) params.status = filters.status
    const res = await listInspections(params)
    rows.value = res.items ?? []
    total.value = res.total ?? 0
  } catch (err) {
    ElMessage.error(errorText(err, '加载巡检记录失败'))
  } finally {
    loading.value = false
  }
}

function onSearch() {
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

function openTriggerDialog() {
  if (!store.canOperate) {
    ElMessage.warning('当前角色无权触发巡检')
    return
  }
  triggerTargetId.value = filters.target_id === '' ? '' : filters.target_id
  triggerVisible.value = true
}

async function confirmTrigger() {
  const targetId = triggerTargetId.value
  if (targetId === '') {
    ElMessage.warning('请选择巡检目标')
    return
  }
  triggering.value = true
  try {
    await triggerInspection(targetId)
    ElMessage.success('已触发巡检')
    triggerVisible.value = false
    page.value = 1
    await load()
  } catch (err) {
    ElMessage.error(errorText(err, '触发巡检失败'))
  } finally {
    triggering.value = false
  }
}

function goDetail(run: InspectionRun) {
  router.push(`/inspections/${run.id}`)
}

onMounted(async () => {
  await loadTargets()
  await load()
})
</script>

<template>
  <div class="vi-page">
    <div class="vi-page-header">
      <h2 class="vi-page-title">巡检记录</h2>
      <div class="vi-toolbar">
        <el-select
          v-model="filters.target_id"
          placeholder="全部目标"
          style="width: 200px"
          @change="onSearch"
        >
          <el-option label="全部目标" value="" />
          <el-option v-for="t in targets" :key="t.id" :label="t.name" :value="t.id" />
        </el-select>
        <el-select
          v-model="filters.status"
          placeholder="全部状态"
          style="width: 140px"
          @change="onSearch"
        >
          <el-option
            v-for="opt in STATUS_OPTIONS"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
        <el-button @click="load">刷新</el-button>
        <el-button type="primary" :disabled="!store.canOperate" @click="openTriggerDialog">
          立即巡检
        </el-button>
      </div>
    </div>

    <div class="vi-card">
      <el-table v-loading="loading" :data="rows" border stripe style="width: 100%">
        <el-table-column prop="id" label="运行 ID" width="90" align="center">
          <template #default="{ row }">
            <span class="vi-mono">#{{ row.id }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="target_id" label="目标" width="90" align="center">
          <template #default="{ row }">
            <span class="vi-mono">#{{ row.target_id }}</span>
          </template>
        </el-table-column>
        <el-table-column label="触发方式" width="100" align="center">
          <template #default="{ row }">{{ triggerTypeText(row.trigger_type) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="110" align="center">
          <template #default="{ row }">
            <StatusTag kind="run" :status="row.status" />
          </template>
        </el-table-column>
        <el-table-column label="开始时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.started_at) }}</template>
        </el-table-column>
        <el-table-column label="耗时" width="120" align="right">
          <template #default="{ row }">{{ formatDuration(row.duration_ms) }}</template>
        </el-table-column>
        <el-table-column label="严重" width="80" align="center">
          <template #default="{ row }">
            <span class="num-critical">{{ row.findings_critical ?? 0 }}</span>
          </template>
        </el-table-column>
        <el-table-column label="警告" width="80" align="center">
          <template #default="{ row }">
            <span class="num-warn">{{ row.findings_warn ?? 0 }}</span>
          </template>
        </el-table-column>
        <el-table-column label="提示" width="80" align="center">
          <template #default="{ row }">
            <span class="num-info">{{ row.findings_info ?? 0 }}</span>
          </template>
        </el-table-column>
        <el-table-column label="错误数" width="90" align="center">
          <template #default="{ row }">
            <span :class="row.error_count ? 'num-critical' : 'vi-muted'">
              {{ row.error_count ?? 0 }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="90" align="center" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="goDetail(asRow<InspectionRun>(row))">详情</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无巡检记录" />
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

    <el-dialog v-model="triggerVisible" title="立即巡检" width="420px">
      <el-form label-width="90px">
        <el-form-item label="巡检目标">
          <el-select
            v-model="triggerTargetId"
            placeholder="请选择目标"
            style="width: 100%"
          >
            <el-option v-for="t in targets" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="triggerVisible = false">取消</el-button>
        <el-button type="primary" :loading="triggering" @click="confirmTrigger">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

.num-critical {
  color: #f56c6c;
  font-weight: 600;
}

.num-warn {
  color: #e6a23c;
  font-weight: 600;
}

.num-info {
  color: #409eff;
  font-weight: 600;
}
</style>
