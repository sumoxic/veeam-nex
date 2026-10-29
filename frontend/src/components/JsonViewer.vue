/**
 * JSON 查看器：折叠展示原始清单，支持整段复制。
 */
<script setup lang="ts">
import { computed, ref } from 'vue'

const props = withDefaults(
  defineProps<{
    data: unknown
    /** 默认展开的层级，超过则折叠 */
    defaultExpanded?: number
    maxHeight?: string
  }>(),
  { defaultExpanded: 2, maxHeight: '520px' },
)

const collapsed = ref(false)

async function copy() {
  try {
    await navigator.clipboard.writeText(text.value)
  } catch {
    // 剪贴板不可用时忽略
  }
}

const text = computed(() => {
  try {
    return JSON.stringify(props.data ?? {}, null, 2) ?? 'null'
  } catch {
    return String(props.data)
  }
})
</script>

<template>
  <div class="vi-json">
    <div class="vi-json-bar">
      <el-button link size="small" @click="collapsed = !collapsed">
        {{ collapsed ? '展开' : '折叠' }}
      </el-button>
      <el-button link size="small" @click="copy">复制</el-button>
    </div>
    <pre v-show="!collapsed" class="vi-json-pre" :style="{ maxHeight }">{{ text }}</pre>
    <el-text v-show="collapsed" truncated class="vi-json-collapsed">{{ text }}</el-text>
  </div>
</template>

<style scoped>
.vi-json {
  border: 1px solid #e8ebf0;
  border-radius: 6px;
  background: #fafbfd;
}

.vi-json-bar {
  display: flex;
  gap: 4px;
  padding: 4px 8px;
  border-bottom: 1px solid #e8ebf0;
}

.vi-json-pre {
  margin: 0;
  padding: 12px;
  overflow: auto;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
}

.vi-json-collapsed {
  display: block;
  padding: 8px 12px;
}
</style>
