/**
 * 远程操作工作台。
 *
 * 安全模型（与后端一致）：
 *   1. 「新建操作」只生成一张操作单并返回一次性确认令牌，**不会**触碰 VBR；
 *   2. 操作员核对预览文本、再输入令牌确认，后端才真正执行；
 *   3. 每一步都落在 operation_audit 表里，可在「操作审计」里回溯。
 */
<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  confirmOperation,
  createOperation,
  listOperationKinds,
  listOperations,
  listTargets,
  rejectOperation,
} from '@/api'
import type { OperationAudit, OperationKind, OperationStatus, Target } from '@/api/types'
import { useUserStore } from '@/stores/user'
import { formatDateTime } from '@/utils/format'
import { asRow } from '@/utils/table'
import { versionLabel } from '@/utils/version'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import JsonViewer from '@/components/JsonViewer.vue'
import StatusTag from '@/components/StatusTag.vue'

/** 建单接口比 OperationAudit 多返回确认令牌与提示文案，这里本地扩展一下 */
interface CreatedOperation extends OperationAudit {
  confirmation_token?: string
  message?: string
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
const kinds = ref<OperationKind[]>([])
const rows = ref<OperationAudit[]>([])
const total = ref(0)
const loading = ref(false)

const filters = reactive<{
  status?: OperationStatus
  kind?: string
  target_id?: number
}>({})
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

async function loadTargets() {
  try {
    const res = await listTargets()
    targets.value = res.items ?? []
  } catch (err) {
    ElMessage.error(errorText(err))
  }
}

async function loadKinds() {
  try {
    const res = await listOperationKinds()
    kinds.value = res.items ?? []
  } catch (err) {
    ElMessage.error(errorText(err))
  }
}

async function load() {
  loading.value = true
  try {
    const res = await listOperations({
      status: filters.status,
      kind: filters.kind,
      target_id: filters.target_id,
      page: page.value,
      size: size.value,
    })
    rows.value = res.items ?? []
    total.value = res.total ?? rows.value.length
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
  loadKinds()
  load()
})

// ---------------------------------------------------------------- 新建操作

const createVisible = ref(false)
const creating = ref(false)
const createForm = reactive<{
  target_id?: number
  kind: string
  idValue?: number
  extraJson: string
}>({
  target_id: undefined,
  kind: '',
  idValue: undefined,
  extraJson: '',
})

const currentKind = computed<OperationKind | undefined>(() =>
  kinds.value.find((k) => k.kind === createForm.kind),
)

const idParamName = computed<string>(() => currentKind.value?.id_param ?? 'id')

function openCreate() {
  createForm.target_id = undefined
  createForm.kind = kinds.value.length ? kinds.value[0].kind : ''
  createForm.idValue = undefined
  createForm.extraJson = ''
  createVisible.value = true
}

function resetCreateForm() {
  createForm.target_id = undefined
  createForm.kind = kinds.value.length ? kinds.value[0].kind : ''
  createForm.idValue = undefined
  createForm.extraJson = ''
}

/** 解析额外参数：必须是 JSON 对象 */
function parseExtraJson(): Record<string, unknown> | null {
  const raw = createForm.extraJson.trim()
  if (!raw) return {}
  try {
    const parsed: unknown = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      ElMessage.error('额外参数必须是一个 JSON 对象')
      return null
    }
    return parsed as Record<string, unknown>
  } catch (err) {
    ElMessage.error(`额外参数不是合法的 JSON：${errorText(err)}`)
    return null
  }
}

async function submitCreate() {
  if (!createForm.target_id) {
    ElMessage.warning('请选择巡检目标')
    return
  }
  if (!createForm.kind) {
    ElMessage.warning('请选择操作类型')
    return
  }
  const extra = parseExtraJson()
  if (extra === null) return

  const params: Record<string, unknown> = {}
  if (createForm.idValue !== undefined) {
    params[idParamName.value] = String(createForm.idValue)
  }
  // JSON 里的同名键优先，方便填 VBR 中的 GUID 实体 ID
  Object.assign(params, extra)

  const idValue = params[idParamName.value]
  if (idValue === undefined || idValue === null || String(idValue).trim() === '') {
    ElMessage.warning(`请填写参数 ${idParamName.value}`)
    return
  }

  creating.value = true
  try {
    const created = (await createOperation({
      target_id: createForm.target_id,
      kind: createForm.kind,
      params,
    })) as CreatedOperation
    createVisible.value = false
    resetCreateForm()
    ElMessage.success('操作单已创建，等待确认')
    await load()
    showCreated(created)
  } catch (err) {
    ElMessage.error(errorText(err))
  } finally {
    creating.value = false
  }
}

// ---------------------------------------------------------------- 建单结果

const createdVisible = ref(false)
const createdInfo = ref<CreatedOperation | null>(null)

function showCreated(row: CreatedOperation) {
  createdInfo.value = row
  createdVisible.value = true
}

async function copyToken() {
  const token = createdInfo.value?.confirmation_token
  if (!token) return
  try {
    await navigator.clipboard?.writeText(token)
    ElMessage.success('确认令牌已复制')
  } catch {
    ElMessage.warning('复制失败，请手动选中令牌复制')
  }
}

// ---------------------------------------------------------------- 确认执行

const confirmVisible = ref(false)
const confirming = ref(false)
const confirmRow = ref<OperationAudit | null>(null)
const confirmToken = ref('')

function openConfirm(row: OperationAudit) {
  confirmRow.value = row
  confirmToken.value = ''
  confirmVisible.value = true
}

async function submitConfirm() {
  const row = confirmRow.value
  if (!row) return
  const token = confirmToken.value.trim()
  if (!token) {
    ElMessage.warning('请输入确认令牌')
    return
  }
  confirming.value = true
  try {
    await confirmOperation(row.request_id, token)
    ElMessage.success('操作已确认并提交执行')
    confirmVisible.value = false
    confirmToken.value = ''
    await load()
  } catch (err) {
    ElMessage.error(errorText(err))
  } finally {
    confirming.value = false
  }
}

// ---------------------------------------------------------------- 拒绝

async function handleReject(row: OperationAudit) {
  try {
    await ElMessageBox.confirm(
      `确定拒绝操作单 ${row.request_id} 吗？拒绝后不可撤销。`,
      '拒绝操作',
      { type: 'warning' },
    )
  } catch {
    return
  }
  try {
    await rejectOperation(row.request_id)
    ElMessage.success('操作单已拒绝')
    await load()
  } catch (err) {
    ElMessage.error(errorText(err))
  }
}

// ---------------------------------------------------------------- 详情

const detailVisible = ref(false)
const detailRow = ref<OperationAudit | null>(null)

function openDetail(row: OperationAudit) {
  detailRow.value = row
  detailVisible.value = true
}
</script>

<template>
  <div class="vi-page">
    <div class="vi-page-header">
      <h2 class="vi-page-title">远程操作</h2>
      <div class="vi-toolbar">
        <el-button v-if="store.canOperate" type="primary" @click="openCreate">新建操作</el-button>
        <el-button @click="handleRefresh">刷新</el-button>
      </div>
    </div>

    <el-alert
      v-if="store.canOperate"
      type="warning"
      :closable="false"
      show-icon
      title="远程操作采用两步确认：新建操作只生成操作单与一次性确认令牌，不会触碰 VBR；需要再次输入令牌才会真正执行。"
      class="vi-ops-alert"
    />

    <div class="vi-card">
      <div class="vi-toolbar vi-ops-filters">
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
          v-model="filters.kind"
          placeholder="全部类型"
          clearable
          style="width: 220px"
          @change="handleFilterChange"
        >
          <el-option
            v-for="item in kinds"
            :key="item.kind"
            :label="`${item.kind} ${item.description}`"
            :value="item.kind"
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

        <el-button @click="handleFilterChange">查询</el-button>
      </div>

      <el-table v-loading="loading" :data="rows" border stripe>
        <el-table-column label="请求 ID" min-width="230">
          <template #default="{ row }">
            <span class="vi-mono">{{ row.request_id }}</span>
          </template>
        </el-table-column>

        <el-table-column label="目标" min-width="160">
          <template #default="{ row }">{{ targetName(row.target_id) }}</template>
        </el-table-column>

        <el-table-column label="类型" min-width="120">
          <template #default="{ row }">
            <span class="vi-mono">{{ row.operation_kind }}</span>
          </template>
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

        <el-table-column label="VBR 任务 ID" min-width="150">
          <template #default="{ row }">
            <span class="vi-mono">{{ row.vbr_task_id || '-' }}</span>
          </template>
        </el-table-column>

        <el-table-column label="错误" min-width="180">
          <template #default="{ row }">
            <span class="vi-muted">{{ row.error_message || '-' }}</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="store.canOperate && row.status === 'pending'"
              link
              type="primary"
              size="small"
              @click="openConfirm(asRow<OperationAudit>(row))"
            >
              确认执行
            </el-button>
            <el-button
              v-if="store.canOperate && row.status === 'pending'"
              link
              type="warning"
              size="small"
              @click="handleReject(asRow<OperationAudit>(row))"
            >
              拒绝
            </el-button>
            <el-button link type="info" size="small" @click="openDetail(asRow<OperationAudit>(row))">详情</el-button>
          </template>
        </el-table-column>

        <template #empty>
          <span class="vi-muted">暂无操作记录</span>
        </template>
      </el-table>

      <el-pagination
        v-model:current-page="page"
        v-model:page-size="size"
        class="vi-ops-pager"
        background
        layout="total, sizes, prev, pager, next"
        :page-sizes="[10, 20, 50, 100]"
        :total="total"
        @current-change="load"
        @size-change="handleRefresh"
      />
    </div>

    <!-- 新建操作 -->
    <el-dialog v-model="createVisible" title="新建操作" width="560px" :close-on-click-modal="false">
      <el-form label-width="110px">
        <el-form-item label="目标" required>
          <el-select v-model="createForm.target_id" placeholder="选择巡检目标" style="width: 100%">
            <el-option
              v-for="item in targets"
              :key="item.id"
              :label="targetOptionLabel(item)"
              :value="item.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="操作类型" required>
          <el-select v-model="createForm.kind" placeholder="选择操作类型" style="width: 100%">
            <el-option
              v-for="item in kinds"
              :key="item.kind"
              :label="`${item.kind} — ${item.description}`"
              :value="item.kind"
            />
          </el-select>
          <div v-if="currentKind" class="vi-muted vi-ops-hint">
            {{ currentKind.description }}，需要参数 {{ currentKind.id_param }}
          </div>
        </el-form-item>

        <el-form-item :label="idParamName">
          <el-input-number
            v-model="createForm.idValue"
            :min="0"
            :precision="0"
            controls-position="right"
            placeholder="实体 ID"
            style="width: 220px"
          />
          <div class="vi-muted vi-ops-hint">
            实体 ID（VBR 中的作业 / 代理标识）。VBR 的 ID 通常是 GUID，可在下方的 JSON 参数里填写
            {{ idParamName }} 覆盖此项。
          </div>
        </el-form-item>

        <el-form-item label="额外参数">
          <el-input
            v-model="createForm.extraJson"
            type="textarea"
            :rows="4"
            placeholder='例如 {"job_id": "8d0f...-...", "perform_active_full": true}'
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button :disabled="creating" @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- 建单结果：确认令牌只在这里出现一次 -->
    <el-dialog v-model="createdVisible" title="操作单已创建" width="560px">
      <el-alert
        type="success"
        :closable="false"
        show-icon
        title="创建操作不会执行任何动作，请核对预览内容后到列表中确认执行。"
      />

      <div class="vi-ops-block">
        <div class="vi-muted">请求 ID</div>
        <div class="vi-mono">{{ createdInfo?.request_id }}</div>
      </div>

      <div class="vi-ops-block">
        <div class="vi-muted">将要执行的内容</div>
        <pre class="vi-mono vi-ops-preview">{{ createdInfo?.preview_text }}</pre>
      </div>

      <div class="vi-ops-block">
        <div class="vi-muted">确认令牌（只显示一次，15 分钟内有效）</div>
        <div class="vi-toolbar">
          <span class="vi-mono vi-ops-token">{{ createdInfo?.confirmation_token || '-' }}</span>
          <el-button
            size="small"
            :disabled="!createdInfo?.confirmation_token"
            @click="copyToken"
          >
            复制令牌
          </el-button>
        </div>
        <div class="vi-muted vi-ops-hint">
          后端不会再次返回该令牌，请立即保存。确认执行时需要原样输入。
        </div>
      </div>

      <template #footer>
        <el-button type="primary" @click="createdVisible = false">知道了</el-button>
      </template>
    </el-dialog>

    <!-- 确认执行 -->
    <ConfirmDialog
      v-model="confirmVisible"
      title="确认执行远程操作"
      message="该操作会真实作用于 VBR 目标，请确认下列内容无误后输入确认令牌。"
      :preview-text="confirmRow?.preview_text ?? ''"
      confirm-text="确认执行"
      :danger="true"
      :loading="confirming"
      @confirm="submitConfirm"
    >
      <div class="vi-ops-block">
        <el-input
          v-model="confirmToken"
          type="password"
          show-password
          placeholder="粘贴建单时返回的确认令牌"
        />
        <div class="vi-muted vi-ops-hint">
          确认令牌只在创建操作单时返回一次，请从建单结果中复制；令牌 15 分钟内有效，过期后需要重新建单。
        </div>
      </div>
    </ConfirmDialog>

    <!-- 详情 -->
    <el-drawer v-model="detailVisible" title="操作单详情" size="560px">
      <div v-if="detailRow" class="vi-ops-detail">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="请求 ID">
            <span class="vi-mono">{{ detailRow.request_id }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="目标">
            {{ targetName(detailRow.target_id) }}
          </el-descriptions-item>
          <el-descriptions-item label="操作类型">
            <span class="vi-mono">{{ detailRow.operation_kind }}</span>
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

        <div class="vi-ops-block">
          <div class="vi-muted">预览内容</div>
          <pre class="vi-mono vi-ops-preview">{{ detailRow.preview_text }}</pre>
        </div>

        <div class="vi-ops-block">
          <div class="vi-muted">参数</div>
          <JsonViewer :data="detailRow.params" />
        </div>

        <div class="vi-ops-block">
          <div class="vi-muted">执行结果</div>
          <JsonViewer :data="detailRow.result ?? {}" />
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
.vi-ops-alert {
  margin-bottom: 12px;
}

.vi-ops-filters {
  margin-bottom: 12px;
}

.vi-ops-pager {
  margin-top: 12px;
  justify-content: flex-end;
}

.vi-ops-hint {
  font-size: 12px;
  line-height: 1.6;
  margin-top: 4px;
}

.vi-ops-block {
  margin-top: 14px;
}

.vi-ops-preview {
  margin: 6px 0 0;
  padding: 12px;
  background: #fafbfd;
  border: 1px solid #e8ebf0;
  border-radius: 6px;
  white-space: pre-wrap;
  word-break: break-all;
  line-height: 1.6;
}

.vi-ops-token {
  padding: 4px 8px;
  background: #fafbfd;
  border: 1px solid #e8ebf0;
  border-radius: 6px;
  word-break: break-all;
}
</style>
