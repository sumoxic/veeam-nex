/**
 * 个人设置：查看自己的账号信息、修改自己的登录口令。
 */
<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { changePassword } from '@/api'
import { useUserStore } from '@/stores/user'
import { formatDateTime } from '@/utils/format'

const store = useUserStore()

const ROLE_LABELS: Record<string, string> = {
  admin: '管理员',
  operator: '操作员',
  viewer: '只读用户',
}

function errorText(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

const roleLabel = computed(() => {
  const role = store.user?.role
  return role ? ROLE_LABELS[role] ?? role : '-'
})

// ---------------------------------------------------------------- 修改口令

const form = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: '',
})

const submitting = ref(false)
const errors = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: '',
})

function validate(): boolean {
  errors.oldPassword = form.oldPassword ? '' : '请输入当前口令'
  errors.newPassword = !form.newPassword
    ? '请输入新口令'
    : form.newPassword.length < 8
      ? '新口令至少 8 位'
      : ''
  errors.confirmPassword = !form.confirmPassword
    ? '请再次输入新口令'
    : form.confirmPassword !== form.newPassword
      ? '两次输入的新口令不一致'
      : ''
  return !errors.oldPassword && !errors.newPassword && !errors.confirmPassword
}

function clearForm() {
  form.oldPassword = ''
  form.newPassword = ''
  form.confirmPassword = ''
  errors.oldPassword = ''
  errors.newPassword = ''
  errors.confirmPassword = ''
}

function onOldPasswordBlur() {
  errors.oldPassword = form.oldPassword ? '' : '请输入当前口令'
}

function onNewPasswordBlur() {
  if (!form.newPassword) {
    errors.newPassword = '请输入新口令'
  } else if (form.newPassword.length < 8) {
    errors.newPassword = '新口令至少 8 位'
  } else {
    errors.newPassword = ''
  }
}

function onConfirmPasswordBlur() {
  if (!form.confirmPassword) {
    errors.confirmPassword = '请再次输入新口令'
  } else if (form.confirmPassword !== form.newPassword) {
    errors.confirmPassword = '两次输入的新口令不一致'
  } else {
    errors.confirmPassword = ''
  }
}

async function submit() {
  if (!validate()) {
    ElMessage.warning('请检查表单填写')
    return
  }
  submitting.value = true
  try {
    await changePassword(form.oldPassword, form.newPassword)
    ElMessage.success('口令已修改')
    clearForm()
  } catch (err) {
    ElMessage.error(errorText(err))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="vi-page">
    <div class="vi-page-header">
      <h2 class="vi-page-title">个人设置</h2>
    </div>

    <div class="vi-card vi-settings-profile">
      <h3 class="vi-settings-subtitle">账号信息</h3>
      <el-descriptions :column="1" border>
        <el-descriptions-item label="用户名">
          <span class="vi-mono">{{ store.user?.username ?? '-' }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="显示名">
          {{ store.user?.display_name || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="邮箱">
          {{ store.user?.email || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="角色">{{ roleLabel }}</el-descriptions-item>
        <el-descriptions-item label="最后登录">
          {{ formatDateTime(store.user?.last_login_at) }}
        </el-descriptions-item>
        <el-descriptions-item label="创建时间">
          {{ formatDateTime(store.user?.created_at) }}
        </el-descriptions-item>
      </el-descriptions>
      <p class="vi-muted vi-settings-note">
        账号信息由管理员维护，如需变更角色或状态请联系管理员。
      </p>
    </div>

    <div class="vi-card vi-settings-pwd">
      <h3 class="vi-settings-subtitle">修改口令</h3>
      <el-form label-width="100px" class="vi-settings-form">
        <el-form-item label="当前口令" required>
          <el-input
            v-model="form.oldPassword"
            type="password"
            show-password
            placeholder="当前登录口令"
            @blur="onOldPasswordBlur"
          />
          <div v-if="errors.oldPassword" class="vi-settings-error">{{ errors.oldPassword }}</div>
        </el-form-item>

        <el-form-item label="新口令" required>
          <el-input
            v-model="form.newPassword"
            type="password"
            show-password
            placeholder="至少 8 位"
            @blur="onNewPasswordBlur"
          />
          <div v-if="errors.newPassword" class="vi-settings-error">{{ errors.newPassword }}</div>
        </el-form-item>

        <el-form-item label="确认新口令" required>
          <el-input
            v-model="form.confirmPassword"
            type="password"
            show-password
            placeholder="再次输入新口令"
            @blur="onConfirmPasswordBlur"
          />
          <div v-if="errors.confirmPassword" class="vi-settings-error">
            {{ errors.confirmPassword }}
          </div>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="submitting" @click="submit">保存</el-button>
          <el-button :disabled="submitting" @click="clearForm">重置</el-button>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<style scoped>
.vi-settings-profile {
  margin-bottom: 16px;
}

.vi-settings-subtitle {
  margin: 0 0 12px;
  font-size: 15px;
  font-weight: 600;
}

.vi-settings-note {
  margin: 12px 0 0;
  font-size: 12px;
}

.vi-settings-form {
  max-width: 520px;
}

.vi-settings-error {
  margin-top: 4px;
  color: #f56c6c;
  font-size: 12px;
  line-height: 1.4;
}
</style>
