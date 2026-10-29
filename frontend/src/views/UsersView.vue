/**
 * 用户管理（仅管理员）。
 *
 * 新建 / 编辑用户资料、重置他人口令、停用账号。
 * 停用走的是 DELETE /users/{id}，后端只把账号标记为停用并吊销令牌，不做物理删除。
 */
<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createUser,
  deleteUser,
  listUsers,
  resetUserPassword,
  updateUser,
} from '@/api'
import type { User, UserRole } from '@/api/types'
import { useUserStore } from '@/stores/user'
import { formatDateTime } from '@/utils/format'
import { asRow } from '@/utils/table'

const store = useUserStore()

const ROLE_OPTIONS: { value: UserRole; label: string }[] = [
  { value: 'admin', label: '管理员' },
  { value: 'operator', label: '操作员' },
  { value: 'viewer', label: '只读用户' },
]

function errorText(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

function roleLabel(role?: string | null): string {
  return ROLE_OPTIONS.find((r) => r.value === role)?.label ?? role ?? '-'
}

const rows = ref<User[]>([])
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const res = await listUsers()
    rows.value = res.items ?? []
  } catch (err) {
    ElMessage.error(errorText(err))
  } finally {
    loading.value = false
  }
}

onMounted(load)

// ---------------------------------------------------------------- 新建 / 编辑

const dialogVisible = ref(false)
const editing = ref(false)
const saving = ref(false)

const form = reactive<{
  id?: number
  username: string
  password: string
  display_name: string
  email: string
  role: UserRole
  is_active: boolean
}>({
  id: undefined,
  username: '',
  password: '',
  display_name: '',
  email: '',
  role: 'viewer',
  is_active: true,
})

function openCreate() {
  editing.value = false
  form.id = undefined
  form.username = ''
  form.password = ''
  form.display_name = ''
  form.email = ''
  form.role = 'viewer'
  form.is_active = true
  dialogVisible.value = true
}

function openEdit(row: User) {
  editing.value = true
  form.id = row.id
  form.username = row.username
  form.password = ''
  form.display_name = row.display_name ?? ''
  form.email = row.email ?? ''
  form.role = row.role
  form.is_active = row.is_active
  dialogVisible.value = true
}

/** el-switch 的事件值可能是 boolean / string / number，统一转成布尔 */
function onActiveChange(value: boolean | string | number) {
  form.is_active = Boolean(value)
}

async function submit() {
  if (!editing.value) {
    const username = form.username.trim()
    if (!username) {
      ElMessage.warning('请填写用户名')
      return
    }
    if (form.password.length < 8) {
      ElMessage.warning('初始口令至少 8 位')
      return
    }
  }

  saving.value = true
  try {
    const userId = form.id
    if (editing.value && userId !== undefined) {
      await updateUser(userId, {
        display_name: form.display_name.trim() || null,
        email: form.email.trim() || null,
        role: form.role,
        is_active: form.is_active,
      })
      ElMessage.success('用户已更新')
    } else {
      await createUser({
        username: form.username.trim(),
        password: form.password,
        display_name: form.display_name.trim() || null,
        email: form.email.trim() || null,
        role: form.role,
      })
      ElMessage.success('用户已创建')
    }
    dialogVisible.value = false
    await load()
  } catch (err) {
    ElMessage.error(errorText(err))
  } finally {
    saving.value = false
  }
}

// ---------------------------------------------------------------- 重置口令

const pwdVisible = ref(false)
const pwdSaving = ref(false)
const pwdTarget = ref<User | null>(null)
const newPassword = ref('')

function openReset(row: User) {
  pwdTarget.value = row
  newPassword.value = ''
  pwdVisible.value = true
}

async function submitReset() {
  const target = pwdTarget.value
  if (!target) return
  if (newPassword.value.length < 8) {
    ElMessage.warning('新口令至少 8 位')
    return
  }
  pwdSaving.value = true
  try {
    await resetUserPassword(target.id, newPassword.value)
    ElMessage.success('口令已重置')
    pwdVisible.value = false
    newPassword.value = ''
    await load()
  } catch (err) {
    ElMessage.error(errorText(err))
  } finally {
    pwdSaving.value = false
  }
}

// ---------------------------------------------------------------- 停用

async function handleDeactivate(row: User) {
  try {
    await ElMessageBox.confirm(
      `确定停用用户「${row.username}」吗？停用后该用户将无法登录，其令牌会被吊销。`,
      '停用用户',
      { type: 'warning' },
    )
  } catch {
    return
  }
  try {
    await deleteUser(row.id)
    ElMessage.success('用户已停用')
    await load()
  } catch (err) {
    ElMessage.error(errorText(err))
  }
}
</script>

<template>
  <div class="vi-page">
    <div class="vi-page-header">
      <h2 class="vi-page-title">用户管理</h2>
      <div class="vi-toolbar">
        <el-button type="primary" @click="openCreate">新建用户</el-button>
        <el-button @click="load">刷新</el-button>
      </div>
    </div>

    <el-alert
      v-if="!store.isAdmin"
      type="info"
      :closable="false"
      show-icon
      title="用户管理仅对管理员开放。"
      class="vi-users-alert"
    />

    <div class="vi-card">
      <el-table v-loading="loading" :data="rows" border stripe>
        <el-table-column label="用户名" min-width="140">
          <template #default="{ row }">
            <span class="vi-mono">{{ row.username }}</span>
          </template>
        </el-table-column>

        <el-table-column label="显示名" min-width="130">
          <template #default="{ row }">{{ row.display_name || '-' }}</template>
        </el-table-column>

        <el-table-column label="邮箱" min-width="180">
          <template #default="{ row }">{{ row.email || '-' }}</template>
        </el-table-column>

        <el-table-column label="角色" width="110">
          <template #default="{ row }">
            <el-tag size="small" effect="light" :type="row.role === 'admin' ? 'danger' : 'info'">
              {{ roleLabel(row.role) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag size="small" effect="light" :type="row.is_active ? 'success' : 'info'">
              {{ row.is_active ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="最后登录" width="170">
          <template #default="{ row }">{{ formatDateTime(row.last_login_at) }}</template>
        </el-table-column>

        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>

        <el-table-column label="操作" width="210" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openEdit(asRow<User>(row))">编辑</el-button>
            <el-button link type="warning" size="small" @click="openReset(asRow<User>(row))">重置口令</el-button>
            <el-button
              v-if="row.is_active"
              link
              type="danger"
              size="small"
              @click="handleDeactivate(asRow<User>(row))"
            >
              停用
            </el-button>
          </template>
        </el-table-column>

        <template #empty>
          <span class="vi-muted">暂无用户</span>
        </template>
      </el-table>
    </div>

    <!-- 新建 / 编辑 -->
    <el-dialog
      v-model="dialogVisible"
      :title="editing ? '编辑用户' : '新建用户'"
      width="520px"
      :close-on-click-modal="false"
    >
      <el-form label-width="90px">
        <el-form-item label="用户名" required>
          <el-input v-model="form.username" :disabled="editing" placeholder="登录用户名" />
        </el-form-item>

        <el-form-item v-if="!editing" label="初始口令" required>
          <el-input
            v-model="form.password"
            type="password"
            show-password
            placeholder="至少 8 位"
          />
        </el-form-item>

        <el-form-item label="显示名">
          <el-input v-model="form.display_name" placeholder="例如 运维值班" />
        </el-form-item>

        <el-form-item label="邮箱">
          <el-input v-model="form.email" placeholder="user@example.com" />
        </el-form-item>

        <el-form-item label="角色">
          <el-select v-model="form.role" style="width: 100%">
            <el-option
              v-for="item in ROLE_OPTIONS"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>

        <el-form-item v-if="editing" label="启用状态">
          <el-switch
            :model-value="form.is_active"
            active-text="启用"
            inactive-text="停用"
            @update:model-value="onActiveChange"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button :disabled="saving" @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">
          {{ editing ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 重置口令 -->
    <el-dialog v-model="pwdVisible" title="重置口令" width="480px" :close-on-click-modal="false">
      <p class="vi-muted">
        将为用户「{{ pwdTarget?.username }}」设置新的登录口令，用户需使用新口令登录。
      </p>
      <el-input
        v-model="newPassword"
        type="password"
        show-password
        placeholder="新口令，至少 8 位"
        @keyup.enter="submitReset"
      />
      <template #footer>
        <el-button :disabled="pwdSaving" @click="pwdVisible = false">取消</el-button>
        <el-button type="primary" :loading="pwdSaving" @click="submitReset">重置口令</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.vi-users-alert {
  margin-bottom: 12px;
}
</style>
