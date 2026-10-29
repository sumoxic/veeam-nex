<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<template>
  <div class="vi-notfound">
    <el-result icon="warning" title="404" sub-title="页面不存在">
      <template #extra>
        <el-button type="primary" @click="router.push('/')">返回首页</el-button>
      </template>
    </el-result>
  </div>
</template>

<style scoped>
.vi-notfound {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: var(--vi-bg);
}
</style>
