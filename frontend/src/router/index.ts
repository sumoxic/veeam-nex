/**
 * 路由表与访问控制。
 *
 * 守卫逻辑：
 *   - 未登录 → 跳 /login，并把原地址记在 query.redirect；
 *   - 已登录访问 /login → 跳回首页；
 *   - 路由声明了 meta.roles 时，角色不匹配 → 跳首页并提示。
 */
import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import type { UserRole } from '@/api/types'

declare module 'vue-router' {
  interface RouteMeta {
    title?: string
    icon?: string
    roles?: UserRole[]
    /** 侧边栏是否隐藏该项 */
    hidden?: boolean
  }
}

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { title: '登录', hidden: true },
  },
  {
    path: '/',
    component: () => import('@/layouts/DefaultLayout.vue'),
    children: [
      {
        path: '',
        name: 'dashboard',
        component: () => import('@/views/DashboardView.vue'),
        meta: { title: '仪表盘', icon: 'Odometer' },
      },
      {
        path: 'targets',
        name: 'targets',
        component: () => import('@/views/TargetsView.vue'),
        meta: { title: '巡检目标', icon: 'Coin' },
      },
      {
        path: 'targets/:id',
        name: 'target-detail',
        component: () => import('@/views/TargetDetailView.vue'),
        meta: { title: '目标详情', hidden: true },
      },
      {
        path: 'inspections',
        name: 'inspections',
        component: () => import('@/views/InspectionsView.vue'),
        meta: { title: '巡检记录', icon: 'Document' },
      },
      {
        path: 'inspections/:id',
        name: 'inspection-detail',
        component: () => import('@/views/InspectionDetailView.vue'),
        meta: { title: '巡检详情', hidden: true },
      },
      {
        path: 'findings',
        name: 'findings',
        component: () => import('@/views/FindingsView.vue'),
        meta: { title: '发现项', icon: 'Warning' },
      },
      {
        path: 'rules',
        name: 'rules',
        component: () => import('@/views/RulesView.vue'),
        meta: { title: '巡检规则', icon: 'SetUp' },
      },
      {
        path: 'alert-rules',
        name: 'alert-rules',
        component: () => import('@/views/AlertRulesView.vue'),
        meta: { title: '告警规则', icon: 'Bell' },
      },
      {
        path: 'channels',
        name: 'channels',
        component: () => import('@/views/ChannelsView.vue'),
        meta: { title: '通知渠道', icon: 'Connection' },
      },
      {
        path: 'alert-events',
        name: 'alert-events',
        component: () => import('@/views/AlertEventsView.vue'),
        meta: { title: '告警事件', icon: 'Message' },
      },
      {
        path: 'operations',
        name: 'operations',
        component: () => import('@/views/OperationsView.vue'),
        meta: { title: '远程操作', icon: 'Operation' },
      },
      {
        path: 'audit',
        name: 'audit',
        component: () => import('@/views/AuditView.vue'),
        meta: { title: '操作审计', icon: 'Finished', roles: ['admin'] },
      },
      {
        path: 'users',
        name: 'users',
        component: () => import('@/views/UsersView.vue'),
        meta: { title: '用户管理', icon: 'User', roles: ['admin'] },
      },
      {
        path: 'settings',
        name: 'settings',
        component: () => import('@/views/SettingsView.vue'),
        meta: { title: '个人设置', icon: 'Setting' },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/views/NotFoundView.vue'),
    meta: { title: '页面不存在', hidden: true },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  const store = useUserStore()
  await store.restore()

  if (to.path === '/login') {
    return store.isLoggedIn ? { path: '/' } : true
  }
  if (!store.isLoggedIn) {
    return { path: '/login', query: to.fullPath === '/' ? {} : { redirect: to.fullPath } }
  }

  const required = to.meta.roles
  if (required?.length && store.role && !required.includes(store.role)) {
    ElMessage.warning('当前角色无权访问该页面')
    return { path: '/' }
  }
  return true
})

router.afterEach((to) => {
  const title = to.meta.title
  document.title = title ? `${title} · Veeam VBR 巡检平台` : 'Veeam VBR 巡检平台'
})

export default router
