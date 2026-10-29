/**
 * 全局用户状态：登录信息、角色、令牌。
 *
 * 令牌存放在 localStorage（见 api/client.ts），这里只保存用户档案，
 * 页面刷新后通过 /auth/me 重新拉取，保证角色判断始终以服务端为准。
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { ApiError, clearTokens, writeTokens } from '@/api/client'
import { fetchMe, login as loginApi, logout as logoutApi } from '@/api'
import type { User, UserRole } from '@/api/types'

export const useUserStore = defineStore('user', () => {
  const user = ref<User | null>(null)
  const loading = ref(false)

  const isLoggedIn = computed(() => Boolean(user.value))
  const role = computed<UserRole | null>(() => user.value?.role ?? null)
  const isAdmin = computed(() => role.value === 'admin')
  const canOperate = computed(() => role.value === 'admin' || role.value === 'operator')

  async function login(username: string, password: string) {
    loading.value = true
    try {
      const result = await loginApi(username, password)
      // 持久化令牌：页面刷新 / Vite 依赖重优化整页 reload 后仍能恢复会话
      writeTokens(result.access_token, result.refresh_token)
      user.value = result.user ?? null
      if (!user.value) user.value = await fetchMe()
      return user.value
    } finally {
      loading.value = false
    }
  }

  /** 页面刷新后补拉用户档案；无本地令牌时也试一次，兼容仅凭 HttpOnly Cookie 的会话 */
  async function restore() {
    if (user.value) return null
    try {
      user.value = await fetchMe()
    } catch (err) {
      if (err instanceof ApiError && err.code === 40100) {
        clearTokens()
      }
      user.value = null
    }
    return user.value
  }

  async function logout() {
    try {
      await logoutApi()
    } catch {
      // 服务端登出失败也要清掉本地令牌，避免卡在无效状态
    }
    clearTokens()
    user.value = null
  }

  return { user, loading, isLoggedIn, role, isAdmin, canOperate, login, logout, restore }
})
