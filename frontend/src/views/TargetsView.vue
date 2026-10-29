/**
 * 巡检目标列表页。
 *
 * 说明：后端 `GET /targets` 只支持 `q` / `enabled` 两个过滤条件，不接受 page/size，
 * 因此这里的分页在拿到全量结果后由前端切片完成（total 即过滤后的条数）。
 */
<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import DataTablePage from '@/components/DataTablePage.vue'
import JsonViewer from '@/components/JsonViewer.vue'
import StatusTag from '@/components/StatusTag.vue'
import {
  createTarget,
  deleteTarget,
  listTargets,
  testConnection,
  triggerInspection,
  updateSchedule,
  updateTarget,
  type TargetIn,
} from '@/api'
import type { ConnectionTestResult, Target } from '@/api/types'
import { useUserStore } from '@/stores/user'
import { formatDateTime } from '@/utils/format'
import { asRow } from '@/utils/table'

type EnabledFilter = 'all' | 'enabled' | 'disabled'

type TargetForm = {
  name: string
  host: string
  port: number
  username: string
  password: string
  verify_tls: boolean
  description: string
  is_enabled: boolean
  schedule_cron: string
  schedule_timezone: string
  schedule_enabled: boolean
}

const router = useRouter()
const store = useUserStore()

function errMsg(err: unknown): string {
  return err instanceof Error ? err.message : '操作失败'
}

// ------------------------------------------------------------------ 列表状态

const loading = ref(false)
const rows = ref<Target[]>([])
const keyword = ref('')
const enabledFilter = ref<EnabledFilter>('all')
const page = ref(1)
const size = ref(20)

const total = computed(() => rows.value.length)

const pageRows = computed(() => {
  const start = (page.value - 1) * size.value
  return rows.value.slice(start, start + size.value)
})

async function load() {
  loading.value = true
  try {
    const res = await listTargets({
      q: keyword.value.trim() || undefined,
      enabled:
        enabledFilter.value === 'all' ? undefined : enabledFilter.value === 'enabled',
    })
    rows.value = res.items ?? []
    const count = rows.value.length
    const maxPage = Math.max(1, Math.ceil(count / size.value))
    if (page.value > maxPage) page.value = maxPage
  } catch (err) {
    ElMessage.error(errMsg(err))
  } finally {
    loading.value = false
  }
}

function applySearch() {
  page.value = 1
  void load()
}

function onPageChange(value: number) {
  page.value = value
}

function onSizeChange(value: number) {
  size.value = value
  page.value = 1
}

function goDetail(row: Target) {
  router.push(`/targets/${row.id}`)
}

// ------------------------------------------------------------------ 行内操作

async function toggleEnabled(row: Target, value: boolean | string | number) {
  const next = Boolean(value)
  try {
    await updateTarget(row.id, { is_enabled: next })
    // 开关用的是 :model-value，需要手动回填最新状态
    row.is_enabled = next
    ElMessage.success(next ? '目标已启用' : '目标已禁用')
  } catch (err) {
    ElMessage.error(errMsg(err))
  }
}

async function runNow(row: Target) {
  try {
    await triggerInspection(row.id)
    ElMessage.success('已提交巡检任务，结果可在「巡检记录」中查看')
    await load()
  } catch (err) {
    ElMessage.error(errMsg(err))
  }
}

async function removeTarget(row: Target) {
  try {
    await ElMessageBox.confirm(
      `确定要删除目标「${row.name}」吗？其运行记录与发现项会一并删除，且不可恢复。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await deleteTarget(row.id)
    ElMessage.success('目标已删除')
    await load()
  } catch (err) {
    ElMessage.error(errMsg(err))
  }
}

// ------------------------------------------------------------------ 连通性测试

const testVisible = ref(false)
const testingId = ref<number | null>(null)
const testResult = ref<ConnectionTestResult | null>(null)

async function testTarget(row: Target) {
  testingId.value = row.id
  testResult.value = null
  try {
    testResult.value = await testConnection(row.id)
    testVisible.value = true
  } catch (err) {
    ElMessage.error(errMsg(err))
  } finally {
    testingId.value = null
  }
}

// ------------------------------------------------------------------ 新建 / 编辑

const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const editingId = ref<number | null>(null)
const saving = ref(false)
const formRef = ref<FormInstance>()

function emptyForm(): TargetForm {
  return {
    name: '',
    host: '',
    port: 9419,
    username: '',
    password: '',
    verify_tls: false,
    description: '',
    is_enabled: true,
    schedule_cron: '',
    schedule_timezone: 'Asia/Shanghai',
    schedule_enabled: false,
  }
}

const form = ref<TargetForm>(emptyForm())

const rules = computed<FormRules<TargetForm>>(() => ({
  name: [{ required: true, message: '请输入目标名称', trigger: 'blur' }],
  host: [{ required: true, message: '请输入主机地址或 IP', trigger: 'blur' }],
  port: [{ required: true, message: '请输入端口', trigger: 'blur' }],
  username: [{ required: true, message: '请输入登录账号', trigger: 'blur' }],
  // 编辑时口令留空表示沿用旧口令
  password:
    dialogMode.value === 'create'
      ? [{ required: true, message: '请输入登录口令', trigger: 'blur' }]
      : [],
}))

function resetValidation() {
  void nextTick(() => formRef.value?.clearValidate())
}

function openCreate() {
  dialogMode.value = 'create'
  editingId.value = null
  form.value = emptyForm()
  dialogVisible.value = true
  resetValidation()
}

function openEdit(row: Target) {
  dialogMode.value = 'edit'
  editingId.value = row.id
  form.value = {
    name: row.name,
    host: row.host,
    port: row.port,
    username: row.username,
    password: '',
    verify_tls: row.verify_tls,
    description: row.description ?? '',
    is_enabled: row.is_enabled,
    schedule_cron: row.schedule_cron ?? '',
    schedule_timezone: row.schedule_timezone || 'Asia/Shanghai',
    schedule_enabled: row.schedule_enabled,
  }
  dialogVisible.value = true
  resetValidation()
}

async function save() {
  const instance = formRef.value
  if (!instance) return
  const valid = await instance.validate().catch(() => false)
  if (!valid) return

  saving.value = true
  try {
    const payload: TargetIn = {
      name: form.value.name.trim(),
      host: form.value.host.trim(),
      port: form.value.port,
      username: form.value.username.trim(),
      password: form.value.password,
      verify_tls: form.value.verify_tls,
      description: form.value.description.trim() || null,
      is_enabled: form.value.is_enabled,
      schedule_cron: form.value.schedule_cron.trim() || null,
      schedule_timezone: form.value.schedule_timezone.trim() || 'Asia/Shanghai',
      schedule_enabled: form.value.schedule_enabled,
    }

    if (dialogMode.value === 'create') {
      await createTarget(payload)
      ElMessage.success('目标已创建')
    } else if (editingId.value !== null) {
      const id = editingId.value
      const update: Partial<TargetIn> = {
        name: payload.name,
        host: payload.host,
        port: payload.port,
        username: payload.username,
        verify_tls: payload.verify_tls,
        // 后端忽略 null，置空描述统一传空串
        description: payload.description ?? '',
        is_enabled: payload.is_enabled,
      }
      // 口令留空表示不修改
      if (payload.password) update.password = payload.password
      await updateTarget(id, update)
      // 排期字段后端只在排期接口里可写
      await updateSchedule(id, {
        cron: payload.schedule_cron ?? null,
        timezone: payload.schedule_timezone,
        enabled: payload.schedule_enabled,
      })
      ElMessage.success('目标已更新')
    }

    dialogVisible.value = false
    await load()
  } catch (err) {
    ElMessage.error(errMsg(err))
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <DataTablePage
    title="巡检目标"
    :total="total"
    :page="page"
    :size="size"
    :loading="loading"
    @update:page="onPageChange"
    @update:size="onSizeChange"
    @refresh="load"
  >
    <template #toolbar>
      <el-input
        v-model="keyword"
        placeholder="搜索名称或地址"
        clearable
        style="width: 220px"
        @keyup.enter="applySearch"
        @clear="applySearch"
      />
      <el-select v-model="enabledFilter" style="width: 130px" @change="applySearch">
        <el-option label="全部状态" value="all" />
        <el-option label="已启用" value="enabled" />
        <el-option label="已禁用" value="disabled" />
      </el-select>
      <el-button v-if="store.canOperate" type="primary" @click="openCreate">
        <el-icon><Plus /></el-icon>
        新建目标
      </el-button>
    </template>

    <el-table :data="pageRows" row-key="id" @row-click="goDetail">
      <el-table-column label="名称" prop="name" min-width="160" show-overflow-tooltip />
      <el-table-column label="地址" min-width="180">
        <template #default="{ row }">
          <span class="vi-mono">{{ row.host }}:{{ row.port }}</span>
        </template>
      </el-table-column>
      <el-table-column label="账号" prop="username" min-width="140" show-overflow-tooltip />
      <el-table-column label="启用" width="100">
        <template #default="{ row }">
          <div @click.stop>
            <el-switch
              v-if="store.canOperate"
              :model-value="row.is_enabled"
              @update:model-value="(value: boolean | string | number) => toggleEnabled(asRow<Target>(row), value)"
            />
            <el-tag v-else :type="row.is_enabled ? 'success' : 'info'" size="small" effect="light">
              {{ row.is_enabled ? '启用' : '禁用' }}
            </el-tag>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="排期" min-width="200">
        <template #default="{ row }">
          <template v-if="row.schedule_cron">
            <span class="vi-mono">{{ row.schedule_cron }}</span>
            <span class="vi-muted"> ({{ row.schedule_timezone }})</span>
          </template>
          <span v-else class="vi-muted">-</span>
        </template>
      </el-table-column>
      <el-table-column label="上次运行" min-width="160">
        <template #default="{ row }">{{ formatDateTime(row.last_run_at) }}</template>
      </el-table-column>
      <el-table-column label="上次状态" width="110">
        <template #default="{ row }">
          <StatusTag kind="run" :status="row.last_run_status" />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="300" fixed="right">
        <template #default="{ row }">
          <div class="vi-row-actions" @click.stop>
            <el-button
              v-if="store.canOperate"
              link
              type="primary"
              size="small"
              :loading="testingId === row.id"
              @click="testTarget(asRow<Target>(row))"
            >
              测试连通性
            </el-button>
            <el-button
              v-if="store.canOperate"
              link
              type="primary"
              size="small"
              @click="runNow(asRow<Target>(row))"
            >
              立即巡检
            </el-button>
            <el-button v-if="store.canOperate" link type="primary" size="small" @click="openEdit(asRow<Target>(row))">
              编辑
            </el-button>
            <el-button v-if="store.canOperate" link type="danger" size="small" @click="removeTarget(asRow<Target>(row))">
              删除
            </el-button>
            <el-button link type="info" size="small" @click="goDetail(asRow<Target>(row))">详情</el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>
  </DataTablePage>

  <!-- 新建 / 编辑目标 -->
  <el-dialog
    v-model="dialogVisible"
    :title="dialogMode === 'create' ? '新建巡检目标' : '编辑巡检目标'"
    width="620px"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
      <el-form-item label="名称" prop="name">
        <el-input v-model="form.name" placeholder="例如：总部 VBR" />
      </el-form-item>
      <el-form-item label="地址" prop="host">
        <el-input v-model="form.host" placeholder="VBR 服务器 IP 或域名" />
      </el-form-item>
      <el-form-item label="端口" prop="port">
        <el-input-number v-model="form.port" :min="1" :max="65535" controls-position="right" />
      </el-form-item>
      <el-form-item label="账号" prop="username">
        <el-input v-model="form.username" placeholder="VBR 登录账号" />
      </el-form-item>
      <el-form-item label="口令" prop="password">
        <el-input
          v-model="form.password"
          type="password"
          show-password
          :placeholder="dialogMode === 'create' ? '请输入登录口令' : '留空表示沿用原口令'"
        />
      </el-form-item>
      <el-form-item label="校验 TLS">
        <el-switch v-model="form.verify_tls" />
      </el-form-item>
      <el-form-item label="描述">
        <el-input
          v-model="form.description"
          type="textarea"
          :rows="2"
          maxlength="512"
          show-word-limit
        />
      </el-form-item>
      <el-form-item label="启用">
        <el-switch v-model="form.is_enabled" />
      </el-form-item>
      <el-form-item label="排期 Cron">
        <el-input v-model="form.schedule_cron" placeholder="5 段标准 cron，例如 0 2 * * *" />
      </el-form-item>
      <el-form-item label="时区">
        <el-input v-model="form.schedule_timezone" placeholder="Asia/Shanghai" />
      </el-form-item>
      <el-form-item label="启用排期">
        <el-switch v-model="form.schedule_enabled" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="save">保存</el-button>
    </template>
  </el-dialog>

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
      <div class="vi-section-title">服务器信息</div>
      <JsonViewer :data="testResult.server" />
    </template>
    <template #footer>
      <el-button @click="testVisible = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.vi-row-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.vi-section-title {
  margin: 12px 0 8px;
  font-weight: 600;
}

.vi-error-text {
  color: #f56c6c;
}
</style>
