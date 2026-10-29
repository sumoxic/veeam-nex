<script setup lang="ts">
/**
 * 登录页：账号口令登录，登录成功后跳回原访问地址（route.query.redirect）。
 */
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const store = useUserStore()

const formRef = ref<FormInstance>()
const form = reactive({ username: '', password: '' })

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入口令', trigger: 'blur' }],
}

/** 登录失败时优先展示后端返回的业务错误信息 */
function errorMessage(err: unknown, fallback: string): string {
  if (err instanceof Error && err.message) return err.message
  return fallback
}

async function handleLogin() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  try {
    await store.login(form.username, form.password)
    ElMessage.success('登录成功')
    const redirect = route.query.redirect
    const target = typeof redirect === 'string' && redirect ? redirect : '/'
    await router.replace(target)
  } catch (err) {
    ElMessage.error(errorMessage(err, '登录失败，请稍后重试'))
  }
}
</script>

<template>
  <div class="login-page">
    <div class="orb orb-a" />
    <div class="orb orb-b" />
    <div class="orb orb-c" />
    <div class="grid-veil" />

    <div class="login-shell">
      <section class="login-story">
        <div class="story-brand">
          <span class="brand-mark">V</span>
          <span class="brand-name">Veeam Inspector</span>
        </div>

        <h1 class="story-title">
          让每一次巡检<br />
          <span class="grad-text">都看得见。</span>
        </h1>

        <p class="story-sub">
          面向 Veeam Backup &amp; Replication 的巡检与告警平台。
          作业状态、存储库容量、还原点时效与风险发现，一屏尽览。
        </p>

        <ul class="story-points">
          <li>
            <span class="point-mark blue"><el-icon><Odometer /></el-icon></span>
            <div>
              <b>按轮次回看</b>
              <small>任意一次巡检的 VBR 状态都可完整复现</small>
            </div>
          </li>
          <li>
            <span class="point-mark green"><el-icon><SetUp /></el-icon></span>
            <div>
              <b>规则驱动发现项</b>
              <small>阈值可覆盖，问题跨轮次去重与自动恢复</small>
            </div>
          </li>
          <li>
            <span class="point-mark amber"><el-icon><Bell /></el-icon></span>
            <div>
              <b>告警闭环</b>
              <small>冷却与去重窗口，级别升级自动触达</small>
            </div>
          </li>
        </ul>

        <div class="story-foot">
          <span class="dot-live" />
          VEEAM VBR · INSPECTION PLATFORM
        </div>
      </section>

      <section class="login-panel">
        <div class="panel-halo" />
        <div class="login-card">
          <div class="card-head">
            <h2>登录平台</h2>
            <p>使用管理员或操作员账号继续</p>
          </div>

          <el-form
            ref="formRef"
            :model="form"
            :rules="rules"
            label-position="top"
            class="login-form"
            @submit.prevent="handleLogin"
          >
            <el-form-item label="用户名" prop="username">
              <el-input
                v-model="form.username"
                placeholder="请输入用户名"
                size="large"
                clearable
                autofocus
                autocomplete="username"
                @keyup.enter="handleLogin"
              >
                <template #prefix>
                  <el-icon><User /></el-icon>
                </template>
              </el-input>
            </el-form-item>

            <el-form-item label="口令" prop="password">
              <el-input
                v-model="form.password"
                type="password"
                placeholder="请输入口令"
                size="large"
                show-password
                autocomplete="current-password"
                @keyup.enter="handleLogin"
              >
                <template #prefix>
                  <el-icon><Lock /></el-icon>
                </template>
              </el-input>
            </el-form-item>

            <el-button
              class="login-submit"
              type="primary"
              size="large"
              :loading="store.loading"
              @click="handleLogin"
            >
              <span>进入平台</span>
              <el-icon v-if="!store.loading" class="submit-arrow"><Right /></el-icon>
            </el-button>
          </el-form>

          <p class="login-hint">会话由 HttpOnly Cookie 与访问令牌双重维护</p>
        </div>

        <p class="login-copyright">© 2026 Veeam Inspector · 局域网部署</p>
      </section>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  position: relative;
  min-height: 100vh;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px;
  background: #f7f6f4;
}

/* ---------------- 背景氛围 ---------------- */

.orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(90px);
  opacity: 0.5;
  pointer-events: none;
  animation: float 22s ease-in-out infinite;
}

.orb-a {
  width: 520px;
  height: 520px;
  top: -180px;
  left: -120px;
  background: radial-gradient(circle, #6b8bff 0%, transparent 68%);
}

.orb-b {
  width: 460px;
  height: 460px;
  bottom: -160px;
  right: -80px;
  background: radial-gradient(circle, #f2af63 0%, transparent 68%);
  animation-delay: -7s;
}

.orb-c {
  width: 380px;
  height: 380px;
  top: 38%;
  left: 46%;
  background: radial-gradient(circle, #79bd89 0%, transparent 70%);
  opacity: 0.35;
  animation-delay: -13s;
}

@keyframes float {
  0%,
  100% {
    transform: translate3d(0, 0, 0) scale(1);
  }
  33% {
    transform: translate3d(26px, -24px, 0) scale(1.05);
  }
  66% {
    transform: translate3d(-20px, 18px, 0) scale(0.97);
  }
}

.grid-veil {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background-image:
    linear-gradient(rgba(32, 33, 36, 0.035) 1px, transparent 1px),
    linear-gradient(90deg, rgba(32, 33, 36, 0.035) 1px, transparent 1px);
  background-size: 56px 56px;
  mask-image: radial-gradient(ellipse at 50% 45%, #000 0%, transparent 72%);
  -webkit-mask-image: radial-gradient(ellipse at 50% 45%, #000 0%, transparent 72%);
}

/* ---------------- 结构 ---------------- */

.login-shell {
  position: relative;
  z-index: 2;
  width: 100%;
  max-width: 1080px;
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(380px, 0.95fr);
  gap: 56px;
  align-items: center;
}

/* ---------------- 左侧叙事 ---------------- */

.login-story {
  animation: vi-rise 0.8s cubic-bezier(0.22, 1, 0.36, 1) both;
}

.story-brand {
  display: inline-flex;
  align-items: center;
  gap: 11px;
  margin-bottom: 34px;
}

.brand-mark {
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  border-radius: 12px;
  background: linear-gradient(135deg, #4d6bfe 0%, #7c6cf0 58%, #58bcc8 100%);
  color: #fff;
  font-size: 17px;
  font-weight: 700;
  box-shadow: 0 10px 24px -10px rgba(77, 107, 254, 0.7);
}

.brand-name {
  font-size: 15px;
  font-weight: 650;
  letter-spacing: -0.01em;
  color: var(--vi-heading);
}

.story-title {
  margin: 0;
  font-size: clamp(36px, 4.4vw, 54px);
  line-height: 1.08;
  font-weight: 700;
  letter-spacing: -0.045em;
  color: var(--vi-heading);
}

.grad-text {
  background: linear-gradient(100deg, #4d6bfe 0%, #7c6cf0 45%, #58bcc8 90%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.story-sub {
  margin: 22px 0 32px;
  max-width: 460px;
  font-size: 14.5px;
  line-height: 1.75;
  color: var(--vi-text-2);
}

.story-points {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.story-points li {
  display: flex;
  align-items: flex-start;
  gap: 13px;
}

.point-mark {
  width: 38px;
  height: 38px;
  flex: none;
  display: grid;
  place-items: center;
  border-radius: 12px;
  font-size: 17px;
}

.point-mark.blue {
  background: #eef1ff;
  color: #4d6bfe;
}

.point-mark.green {
  background: #e9f5ee;
  color: #3f8f5c;
}

.point-mark.amber {
  background: #fdf3e2;
  color: #b7791f;
}

.story-points b {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: var(--vi-heading);
}

.story-points small {
  display: block;
  margin-top: 2px;
  font-size: 12.5px;
  color: var(--vi-muted);
}

.story-foot {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-top: 44px;
  font-size: 10.5px;
  letter-spacing: 0.18em;
  font-weight: 600;
  color: var(--vi-muted);
}

.dot-live {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #3fbf7f;
  box-shadow: 0 0 0 4px rgba(63, 191, 127, 0.14);
}

/* ---------------- 右侧登录卡 ---------------- */

.login-panel {
  position: relative;
  animation: vi-rise 0.8s cubic-bezier(0.22, 1, 0.36, 1) 0.12s both;
}

.panel-halo {
  position: absolute;
  inset: -30px;
  border-radius: 40px;
  background: linear-gradient(145deg, rgba(77, 107, 254, 0.1), rgba(242, 175, 99, 0.1));
  filter: blur(28px);
  pointer-events: none;
}

.login-card {
  position: relative;
  padding: 34px 32px 28px;
  border-radius: 26px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(255, 255, 255, 0.9);
  box-shadow:
    0 1px 2px rgba(18, 20, 23, 0.04),
    0 30px 70px -30px rgba(18, 20, 23, 0.3);
  backdrop-filter: blur(22px) saturate(1.2);
}

.card-head h2 {
  margin: 0;
  font-size: 22px;
  font-weight: 650;
  letter-spacing: -0.03em;
  color: var(--vi-heading);
}

.card-head p {
  margin: 6px 0 0;
  font-size: 12.5px;
  color: var(--vi-muted);
}

.login-form {
  margin-top: 24px;
}

.login-form :deep(.el-form-item) {
  margin-bottom: 18px;
}

.login-form :deep(.el-input__wrapper) {
  min-height: 46px;
  border-radius: 13px;
  background: rgba(244, 243, 240, 0.9);
}

.login-form :deep(.el-input__inner) {
  font-size: 14px;
}

.login-form :deep(.el-icon) {
  color: var(--vi-muted);
}

.login-submit {
  width: 100%;
  height: 46px;
  margin-top: 6px;
  border-radius: 13px;
  font-size: 14px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: var(--vi-dark);
  border-color: var(--vi-dark);
  box-shadow: 0 16px 30px -16px rgba(26, 22, 21, 0.8);
  transition: transform 0.2s, background 0.2s, box-shadow 0.2s;
}

.login-submit:hover {
  background: #2d2927;
  border-color: #2d2927;
  transform: translateY(-1px);
  box-shadow: 0 20px 34px -16px rgba(26, 22, 21, 0.7);
}

.login-submit:active {
  transform: translateY(0) scale(0.99);
}

.submit-arrow {
  transition: transform 0.2s;
}

.login-submit:hover .submit-arrow {
  transform: translateX(3px);
}

.login-hint {
  margin: 18px 0 0;
  text-align: center;
  font-size: 11px;
  color: var(--vi-muted);
}

.login-copyright {
  margin: 18px 0 0;
  text-align: center;
  font-size: 10.5px;
  letter-spacing: 0.04em;
  color: var(--vi-muted);
}

/* ---------------- 响应式 ---------------- */

@media (max-width: 940px) {
  .login-page {
    padding: 20px;
  }

  .login-shell {
    grid-template-columns: 1fr;
    max-width: 420px;
    gap: 0;
  }

  .login-story {
    display: none;
  }
}

@media (prefers-reduced-motion: reduce) {
  .login-story,
  .login-panel,
  .orb {
    animation: none;
  }
}
</style>
