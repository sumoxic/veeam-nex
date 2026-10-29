<script setup lang="ts">
/**
 * 主框架布局：左侧导航 + 顶部信息栏 + 内容区。
 *
 * 菜单项按登录用户的角色过滤（router meta.roles），viewer 看不到写操作页面。
 */
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const store = useUserStore()
const collapsed = ref(false)

interface MenuEntry {
  path: string
  title: string
  icon: string
  roles?: string[]
}

const menuGroups = computed<MenuEntry[]>(() => {
  const groups: MenuEntry[] = [
    { path: '/', title: '仪表盘', icon: 'Odometer' },
    { path: '/targets', title: '巡检目标', icon: 'Coin' },
    { path: '/inspections', title: '巡检记录', icon: 'Document' },
    { path: '/findings', title: '发现项', icon: 'Warning' },
    { path: '/rules', title: '巡检规则', icon: 'SetUp' },
    { path: '/alert-rules', title: '告警规则', icon: 'Bell' },
    { path: '/channels', title: '通知渠道', icon: 'Connection' },
    { path: '/alert-events', title: '告警事件', icon: 'Message' },
    { path: '/operations', title: '远程操作', icon: 'Operation' },
    { path: '/audit', title: '操作审计', icon: 'Finished', roles: ['admin'] },
    { path: '/users', title: '用户管理', icon: 'User', roles: ['admin'] },
    { path: '/settings', title: '个人设置', icon: 'Setting' },
  ]
  const role = store.role
  if (!role) return groups
  return groups.filter((g) => !g.roles || g.roles.includes(role))
})

const activePath = computed(() => {
  // 子路由（目标详情 / 巡检详情）高亮父级菜单
  const path = route.path
  if (path.startsWith('/targets')) return '/targets'
  if (path.startsWith('/inspections')) return '/inspections'
  return path
})

const ROLE_LABELS: Record<string, string> = {
  admin: '管理员',
  operator: '操作员',
  viewer: '只读用户',
}

const roleLabel = computed(() => (store.role ? ROLE_LABELS[store.role] ?? store.role : ''))

const initials = computed(() => {
  const name = store.user?.display_name || store.user?.username || ''
  return name ? name.slice(0, 1).toUpperCase() : '?'
})

async function handleLogout() {
  try {
    await ElMessageBox.confirm('确定要退出登录吗？', '提示', { type: 'warning' })
  } catch {
    return
  }
  await store.logout()
  ElMessage.success('已退出登录')
  router.push('/login')
}
</script>

<template>
  <el-container class="vi-layout">
    <el-aside :width="collapsed ? '78px' : '238px'" class="vi-aside">
      <button type="button" class="brand" @click="router.push('/')">
        <span class="brand-mark">V</span>
        <span v-show="!collapsed" class="brand-text">
          <strong>Veeam Inspector</strong>
          <small>VBR 巡检平台</small>
        </span>
      </button>

      <nav class="nav">
        <div v-show="!collapsed" class="nav-label">工作台</div>
        <el-menu
          :default-active="activePath"
          :collapse="collapsed"
          :collapse-transition="false"
          router
          class="vi-menu"
        >
          <el-menu-item v-for="item in menuGroups" :key="item.path" :index="item.path">
            <el-icon><component :is="item.icon" /></el-icon>
            <template #title>{{ item.title }}</template>
          </el-menu-item>
        </el-menu>
      </nav>

      <div class="aside-foot">
        <div v-show="!collapsed" class="foot-card">
          <div class="foot-line"><span class="foot-dot" /> 平台运行中</div>
          <small>局域网部署 · v1.0</small>
        </div>
      </div>
    </el-aside>

    <el-container class="vi-body">
      <el-header class="vi-header">
        <div class="header-left">
          <button type="button" class="icon-btn" @click="collapsed = !collapsed">
            <el-icon>
              <Fold v-if="!collapsed" />
              <Expand v-else />
            </el-icon>
          </button>
          <div class="crumb">
            <span>巡检平台</span>
            <i>/</i>
            <strong>{{ route.meta.title ?? '' }}</strong>
          </div>
        </div>

        <div class="header-right">
          <span v-if="store.role" class="role-chip">{{ roleLabel }}</span>
          <el-dropdown @command="(cmd: string) => (cmd === 'logout' ? handleLogout() : router.push(cmd))">
            <button type="button" class="user-chip">
              <span class="avatar">{{ initials }}</span>
              <span v-show="!collapsed" class="user-name">
                {{ store.user?.display_name || store.user?.username || '未登录' }}
              </span>
              <el-icon class="caret"><ArrowDown /></el-icon>
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="/settings">个人设置</el-dropdown-item>
                <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="vi-main">
        <router-view v-slot="{ Component }">
          <transition name="page-fade" mode="out-in">
            <keep-alive :max="6">
              <component :is="Component" :key="route.path" />
            </keep-alive>
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script lang="ts">
export default {
  name: 'DefaultLayout',
}
</script>

<style scoped>
.vi-layout {
  height: 100vh;
  overflow: hidden;
}

/* ---------------- 侧边栏 ---------------- */

.vi-aside {
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.66);
  backdrop-filter: blur(20px) saturate(1.2);
  border-right: 1px solid var(--vi-hairline);
  transition: width 0.28s cubic-bezier(0.22, 1, 0.36, 1);
  overflow: hidden;
}

.brand {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 20px 18px 14px;
  background: none;
  border: none;
  cursor: pointer;
  text-align: left;
  width: 100%;
}

.brand-mark {
  width: 34px;
  height: 34px;
  flex: none;
  display: grid;
  place-items: center;
  border-radius: 11px;
  background: linear-gradient(135deg, #4d6bfe 0%, #7c6cf0 58%, #58bcc8 100%);
  color: #fff;
  font-size: 16px;
  font-weight: 700;
  letter-spacing: -0.02em;
  box-shadow: 0 8px 18px -8px rgba(77, 107, 254, 0.65);
}

.brand-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
  line-height: 1.25;
}

.brand-text strong {
  font-size: 14.5px;
  font-weight: 650;
  letter-spacing: -0.02em;
  color: var(--vi-heading);
  white-space: nowrap;
}

.brand-text small {
  font-size: 10px;
  letter-spacing: 0.14em;
  color: var(--vi-muted);
  text-transform: uppercase;
  white-space: nowrap;
}

.nav {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 4px 0;
}

.nav-label {
  padding: 12px 24px 8px;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--vi-muted);
}

.vi-menu {
  border-right: none;
  background: transparent;
  padding: 0 10px;
}

.vi-menu:not(.el-menu--collapse) {
  width: auto;
}

.vi-menu :deep(.el-menu-item) {
  height: 42px;
  line-height: 42px;
  margin: 3px 0;
  padding: 0 14px !important;
  border-radius: 12px;
  color: var(--vi-text-2);
  font-size: 13.5px;
  font-weight: 500;
  transition: background 0.2s, color 0.2s, transform 0.2s;
}

.vi-menu :deep(.el-menu-item:hover) {
  background: rgba(32, 33, 36, 0.05);
  color: var(--vi-heading);
}

.vi-menu :deep(.el-menu-item.is-active) {
  background: var(--vi-dark);
  color: #fff;
  box-shadow: 0 10px 22px -14px rgba(26, 22, 21, 0.7);
}

.vi-menu :deep(.el-menu-item.is-active .el-icon) {
  color: #fff;
}

.vi-menu :deep(.el-icon) {
  font-size: 17px;
  margin-right: 10px;
  color: var(--vi-muted);
  transition: color 0.2s;
}

.vi-menu :deep(.el-menu-item:hover .el-icon) {
  color: var(--vi-heading);
}

.vi-menu.el-menu--collapse :deep(.el-menu-item) {
  justify-content: center;
  padding: 0 !important;
}

.vi-menu.el-menu--collapse :deep(.el-icon) {
  margin-right: 0;
}

.aside-foot {
  padding: 12px 14px 16px;
}

.foot-card {
  padding: 11px 13px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid var(--vi-hairline);
}

.foot-line {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 12px;
  font-weight: 550;
  color: var(--vi-heading);
}

.foot-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #3fbf7f;
  box-shadow: 0 0 0 4px rgba(63, 191, 127, 0.14);
  animation: foot-pulse 2.6s ease-in-out infinite;
}

@keyframes foot-pulse {
  0%,
  100% {
    box-shadow: 0 0 0 3px rgba(63, 191, 127, 0.14);
  }
  50% {
    box-shadow: 0 0 0 6px rgba(63, 191, 127, 0.05);
  }
}

.foot-card small {
  display: block;
  margin-top: 4px;
  font-size: 10.5px;
  color: var(--vi-muted);
}

/* ---------------- 主区域 ---------------- */

.vi-body {
  min-width: 0;
}

.vi-header {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 0 24px;
  background: rgba(247, 246, 244, 0.72);
  backdrop-filter: blur(18px) saturate(1.2);
  border-bottom: 1px solid var(--vi-hairline);
  z-index: 20;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
}

.icon-btn {
  width: 36px;
  height: 36px;
  display: grid;
  place-items: center;
  border-radius: 11px;
  border: 1px solid var(--vi-hairline);
  background: rgba(255, 255, 255, 0.72);
  color: var(--vi-text-2);
  cursor: pointer;
  transition: background 0.2s, color 0.2s, border-color 0.2s;
}

.icon-btn:hover {
  background: #fff;
  color: var(--vi-heading);
  border-color: var(--vi-border);
}

.crumb {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--vi-muted);
  white-space: nowrap;
  overflow: hidden;
}

.crumb i {
  font-style: normal;
  color: rgba(32, 33, 36, 0.28);
}

.crumb strong {
  font-weight: 600;
  color: var(--vi-heading);
  font-size: 13.5px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.role-chip {
  display: inline-flex;
  align-items: center;
  height: 24px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 550;
  color: var(--vi-muted);
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid var(--vi-hairline);
}

.user-chip {
  display: flex;
  align-items: center;
  gap: 9px;
  height: 40px;
  padding: 4px 12px 4px 4px;
  border-radius: 999px;
  border: 1px solid var(--vi-hairline);
  background: rgba(255, 255, 255, 0.78);
  cursor: pointer;
  transition: box-shadow 0.2s, border-color 0.2s, background 0.2s;
}

.user-chip:hover {
  background: #fff;
  border-color: var(--vi-border);
  box-shadow: var(--vi-shadow-sm);
}

.avatar {
  width: 30px;
  height: 30px;
  flex: none;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: linear-gradient(135deg, #1a1615, #4a4543);
  color: #fff;
  font-size: 12px;
  font-weight: 650;
}

.user-name {
  font-size: 13px;
  font-weight: 550;
  color: var(--vi-heading);
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.caret {
  font-size: 12px;
  color: var(--vi-muted);
}

.vi-main {
  padding: 0;
  overflow-y: auto;
  background: transparent;
}

@media (max-width: 760px) {
  .vi-header {
    padding: 0 14px;
  }

  .role-chip {
    display: none;
  }

  .user-name {
    display: none;
  }
}
</style>
