<script setup lang="ts">
/**
 * 通知渠道：SMTP 邮件与 Webhook 推送的配置。
 *
 * 渠道的形态由 channel_type 决定，config 对象里存放各自的连接参数；
 * 密钥（smtp 口令 / webhook 签名密钥）是独立的 secret 字段，编辑时留空表示保留原密钥。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createChannel,
  deleteChannel,
  listChannels,
  testChannel,
  updateChannel,
  webhookTemplates,
} from '@/api'
import type { NotificationChannel } from '@/api/types'
import { formatDateTime } from '@/utils/format'
import { asRow } from '@/utils/table'
import { useUserStore } from '@/stores/user'

const store = useUserStore()

const TYPE_OPTIONS: { label: string; value: 'smtp' | 'webhook' }[] = [
  { label: 'SMTP 邮件', value: 'smtp' },
  { label: 'Webhook 推送', value: 'webhook' },
]

const TEMPLATE_LABELS: Record<string, string> = {
  generic: '通用 JSON',
  markdown: 'Markdown',
  text: '纯文本',
  dingtalk: '钉钉',
  feishu: '飞书',
  wecom: '企业微信',
}

const SIGN_LABELS: Record<string, string> = {
  none: '不签名',
  dingtalk: '钉钉签名',
  feishu: '飞书签名',
  hmac_sha256: 'HMAC-SHA256',
}

const channels = ref<NotificationChannel[]>([])
const loading = ref(false)
const templates = ref<string[]>([])
const signTypes = ref<string[]>([])

const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const saving = ref(false)
const hasSecret = ref(false)

const form = reactive({
  name: '',
  channel_type: 'smtp' as 'smtp' | 'webhook',
  enabled: true,
  // smtp
  host: '',
  port: 465,
  username: '',
  from_addr: '',
  to_addrs: '',
  use_ssl: true,
  use_starttls: false,
  subject_prefix: '[Veeam巡检]',
  // webhook
  url: '',
  template: 'generic',
  sign_type: 'none',
  headers_text: '',
  // 通用
  secret: '',
})

function errorText(err: unknown, fallback: string): string {
  return err instanceof Error ? err.message : fallback
}

const templateOptions = computed(() => {
  const list = templates.value.length ? templates.value : ['generic']
  return list.map((value) => ({ label: TEMPLATE_LABELS[value] ?? value, value }))
})

const signTypeOptions = computed(() => {
  const list = signTypes.value.length ? signTypes.value : ['none']
  return list.map((value) => ({ label: SIGN_LABELS[value] ?? value, value }))
})

function typeLabel(type: string): string {
  return type === 'smtp' ? 'SMTP 邮件' : 'Webhook 推送'
}

/** 收件人：每行一个地址（同时兼容逗号分隔） */
function parseAddrs(text: string): string[] {
  return text
    .split(/[\n,;]/)
    .map((item) => item.trim())
    .filter(Boolean)
}

/** 附加请求头：每行一个 `Key: Value` */
function parseHeaders(text: string): Record<string, string> {
  const out: Record<string, string> = {}
  for (const line of text.split('\n')) {
    const trimmed = line.trim()
    if (!trimmed) continue
    const idx = trimmed.indexOf(':')
    if (idx <= 0) continue
    const key = trimmed.slice(0, idx).trim()
    const value = trimmed.slice(idx + 1).trim()
    if (key) out[key] = value
  }
  return out
}

function formatHeaders(headers?: Record<string, unknown> | null): string {
  if (!headers) return ''
  return Object.entries(headers)
    .map(([key, value]) => `${key}: ${String(value ?? '')}`)
    .join('\n')
}

function configString(channel: NotificationChannel, key: string): string {
  const value = channel.config?.[key]
  if (value === null || value === undefined) return ''
  return String(value)
}

function configNumber(channel: NotificationChannel, key: string, fallback: number): number {
  const value = channel.config?.[key]
  const num = Number(value)
  return Number.isFinite(num) ? num : fallback
}

function configBool(channel: NotificationChannel, key: string): boolean {
  return Boolean(channel.config?.[key])
}

async function load() {
  loading.value = true
  try {
    const res = await listChannels()
    channels.value = res.items ?? []
  } catch (err) {
    ElMessage.error(errorText(err, '加载通知渠道失败'))
  } finally {
    loading.value = false
  }
}

async function loadTemplates() {
  try {
    const res = await webhookTemplates()
    templates.value = res.templates ?? []
    signTypes.value = res.sign_types ?? []
  } catch {
    // 模板拿不到时退回内置默认值，不影响渠道本身的配置
    templates.value = []
    signTypes.value = []
  }
}

function resetForm() {
  form.name = ''
  form.channel_type = 'smtp'
  form.enabled = true
  form.host = ''
  form.port = 465
  form.username = ''
  form.from_addr = ''
  form.to_addrs = ''
  form.use_ssl = true
  form.use_starttls = false
  form.subject_prefix = '[Veeam巡检]'
  form.url = ''
  form.template = 'generic'
  form.sign_type = 'none'
  form.headers_text = ''
  form.secret = ''
  hasSecret.value = false
}

function openCreate() {
  if (!store.canOperate) {
    ElMessage.warning('当前角色无权新建通知渠道')
    return
  }
  resetForm()
  editingId.value = null
  dialogVisible.value = true
}

function openEdit(channel: NotificationChannel) {
  if (!store.canOperate) {
    ElMessage.warning('当前角色无权修改通知渠道')
    return
  }
  resetForm()
  editingId.value = channel.id
  hasSecret.value = channel.has_secret
  form.name = channel.name
  form.channel_type = channel.channel_type
  form.enabled = channel.enabled
  form.host = configString(channel, 'host')
  form.port = configNumber(channel, 'port', 465)
  form.username = configString(channel, 'username')
  form.from_addr = configString(channel, 'from_addr')
  const addrs = channel.config?.to_addrs
  form.to_addrs = Array.isArray(addrs) ? addrs.map((a) => String(a)).join('\n') : ''
  form.use_ssl = configBool(channel, 'use_ssl')
  form.use_starttls = configBool(channel, 'use_starttls')
  form.subject_prefix = configString(channel, 'subject_prefix')
  form.url = configString(channel, 'url')
  form.template = configString(channel, 'template') || 'generic'
  form.sign_type = configString(channel, 'sign_type') || 'none'
  form.headers_text = formatHeaders(channel.headers)
  dialogVisible.value = true
}

function buildConfig(): Record<string, unknown> {
  if (form.channel_type === 'smtp') {
    return {
      host: form.host.trim(),
      port: form.port,
      username: form.username.trim(),
      from_addr: form.from_addr.trim(),
      to_addrs: parseAddrs(form.to_addrs),
      use_ssl: form.use_ssl,
      use_starttls: form.use_starttls,
      subject_prefix: form.subject_prefix,
    }
  }
  return {
    url: form.url.trim(),
    template: form.template,
    sign_type: form.sign_type,
  }
}

async function onSave() {
  if (!store.canOperate) {
    ElMessage.warning('当前角色无权修改通知渠道')
    return
  }
  if (!form.name.trim()) {
    ElMessage.warning('请填写渠道名称')
    return
  }
  if (form.channel_type === 'smtp' && !form.host.trim()) {
    ElMessage.warning('请填写 SMTP 服务器地址')
    return
  }
  if (form.channel_type === 'webhook' && !form.url.trim()) {
    ElMessage.warning('请填写 Webhook 地址')
    return
  }

  const payload = {
    name: form.name.trim(),
    channel_type: form.channel_type,
    enabled: form.enabled,
    config: buildConfig(),
    // 留空表示保留原有密钥
    secret: form.secret.trim() ? form.secret : null,
    headers: form.channel_type === 'webhook' ? parseHeaders(form.headers_text) : null,
  }

  saving.value = true
  try {
    if (editingId.value === null) {
      await createChannel(payload)
      ElMessage.success('通知渠道已创建')
    } else {
      await updateChannel(editingId.value, payload)
      ElMessage.success('通知渠道已保存')
    }
    dialogVisible.value = false
    await load()
  } catch (err) {
    ElMessage.error(errorText(err, '保存通知渠道失败'))
  } finally {
    saving.value = false
  }
}

/** 后端返回 { ok, error }，这里统一转成提示文案 */
async function onTest(channel: NotificationChannel) {
  if (!store.canOperate) {
    ElMessage.warning('当前角色无权测试通知渠道')
    return
  }
  try {
    const result = await testChannel(channel.id)
    const info = (result ?? {}) as unknown as Record<string, unknown>
    const error = typeof info.error === 'string' ? info.error : ''
    if (info.ok) {
      ElMessage.success(`渠道「${channel.name}」测试发送成功`)
    } else {
      ElMessage.error(error ? `测试失败：${error}` : `渠道「${channel.name}」测试发送失败`)
    }
    await load()
  } catch (err) {
    ElMessage.error(errorText(err, '测试通知渠道失败'))
  }
}

async function onDelete(channel: NotificationChannel) {
  if (!store.canOperate) {
    ElMessage.warning('当前角色无权删除通知渠道')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确定删除通知渠道「${channel.name}」吗？引用了该渠道的告警路由会失效。`,
      '删除通知渠道',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await deleteChannel(channel.id)
    ElMessage.success('通知渠道已删除')
    await load()
  } catch (err) {
    ElMessage.error(errorText(err, '删除通知渠道失败'))
  }
}

onMounted(async () => {
  await loadTemplates()
  await load()
})
</script>

<template>
  <div class="vi-page">
    <div class="vi-page-header">
      <h2 class="vi-page-title">通知渠道</h2>
      <div class="vi-toolbar">
        <el-button @click="load">刷新</el-button>
        <el-button type="primary" :disabled="!store.canOperate" @click="openCreate">
          新建通知渠道
        </el-button>
      </div>
    </div>

    <div class="vi-card">
      <el-table v-loading="loading" :data="channels" border stripe style="width: 100%">
        <el-table-column prop="name" label="名称" min-width="160" show-overflow-tooltip />
        <el-table-column label="类型" width="130" align="center">
          <template #default="{ row }">{{ typeLabel(row.channel_type) }}</template>
        </el-table-column>
        <el-table-column label="启用" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'" size="small" effect="light">
              {{ row.enabled ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="密钥状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.has_secret ? 'success' : 'warning'" size="small" effect="light">
              {{ row.has_secret ? '已配置' : '未配置' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="首次测试" width="170">
          <template #default="{ row }">{{ formatDateTime(row.last_test_at) }}</template>
        </el-table-column>
        <el-table-column label="测试结果" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="!row.last_test_status" class="vi-muted">未测试</span>
            <span v-else :class="row.last_test_status === 'ok' ? 'test-ok' : 'test-failed'">
              {{ row.last_test_status }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" align="center" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" :disabled="!store.canOperate" @click="openEdit(asRow<NotificationChannel>(row))">
              编辑
            </el-button>
            <el-button link type="primary" :disabled="!store.canOperate" @click="onTest(asRow<NotificationChannel>(row))">
              测试
            </el-button>
            <el-button link type="danger" :disabled="!store.canOperate" @click="onDelete(asRow<NotificationChannel>(row))">
              删除
            </el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无通知渠道" />
        </template>
      </el-table>
    </div>

    <el-dialog
      v-model="dialogVisible"
      :title="editingId === null ? '新建通知渠道' : '编辑通知渠道'"
      width="640px"
      top="6vh"
    >
      <el-form label-width="120px" :model="form">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="例如：运维值班邮箱" maxlength="128" />
        </el-form-item>
        <el-form-item label="类型">
          <el-radio-group v-model="form.channel_type">
            <el-radio v-for="opt in TYPE_OPTIONS" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.enabled" />
        </el-form-item>

        <template v-if="form.channel_type === 'smtp'">
          <el-form-item label="服务器" required>
            <el-input v-model="form.host" placeholder="smtp.example.com" />
          </el-form-item>
          <el-form-item label="端口">
            <el-input-number v-model="form.port" :min="1" :max="65535" controls-position="right" />
          </el-form-item>
          <el-form-item label="用户名">
            <el-input v-model="form.username" placeholder="发信账号" />
          </el-form-item>
          <el-form-item label="发件地址">
            <el-input v-model="form.from_addr" placeholder="留空则使用用户名" />
          </el-form-item>
          <el-form-item label="收件地址">
            <el-input
              v-model="form.to_addrs"
              type="textarea"
              :rows="4"
              placeholder="每行一个邮箱地址"
            />
          </el-form-item>
          <el-form-item label="SSL">
            <el-switch v-model="form.use_ssl" />
            <span class="vi-muted unit-hint">SMTPS（通常为 465 端口）</span>
          </el-form-item>
          <el-form-item label="STARTTLS">
            <el-switch v-model="form.use_starttls" />
            <span class="vi-muted unit-hint">STARTTLS（通常为 587 端口）</span>
          </el-form-item>
          <el-form-item label="主题前缀">
            <el-input v-model="form.subject_prefix" placeholder="[Veeam巡检]" />
          </el-form-item>
          <el-form-item label="口令">
            <el-input
              v-model="form.secret"
              type="password"
              show-password
              :placeholder="editingId === null ? 'SMTP 账号口令' : '留空表示保留原口令'"
            />
            <el-tag
              v-if="editingId !== null"
              :type="hasSecret ? 'success' : 'warning'"
              size="small"
              class="secret-tag"
            >
              {{ hasSecret ? '已配置' : '未配置' }}
            </el-tag>
          </el-form-item>
        </template>

        <template v-else>
          <el-form-item label="Webhook 地址" required>
            <el-input v-model="form.url" placeholder="https://example.com/hook" />
          </el-form-item>
          <el-form-item label="消息模板">
            <el-select v-model="form.template" style="width: 220px">
              <el-option
                v-for="opt in templateOptions"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="签名方式">
            <el-select v-model="form.sign_type" style="width: 220px">
              <el-option
                v-for="opt in signTypeOptions"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="附加请求头">
            <el-input
              v-model="form.headers_text"
              type="textarea"
              :rows="3"
              placeholder="每行一个 Key: Value"
            />
          </el-form-item>
          <el-form-item label="签名密钥">
            <el-input
              v-model="form.secret"
              type="password"
              show-password
              :placeholder="editingId === null ? 'Webhook 签名密钥' : '留空表示保留原密钥'"
            />
            <el-tag
              v-if="editingId !== null"
              :type="hasSecret ? 'success' : 'warning'"
              size="small"
              class="secret-tag"
            >
              {{ hasSecret ? '已配置' : '未配置' }}
            </el-tag>
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.unit-hint {
  margin-left: 8px;
  font-size: 12px;
}

.secret-tag {
  margin-left: 8px;
}

.test-ok {
  color: #67c23a;
}

.test-failed {
  color: #f56c6c;
  word-break: break-all;
}
</style>
