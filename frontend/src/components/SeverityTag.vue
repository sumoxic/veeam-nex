/**
 * 级别标签：把 critical / warn / info / ok 映射到统一的颜色语义。
 */
<script setup lang="ts">
import { computed } from 'vue'
import type { Severity } from '@/api/types'

const props = defineProps<{
  level?: Severity | string | null
  size?: 'large' | 'default' | 'small'
}>()

const TYPE_MAP: Record<string, 'danger' | 'warning' | 'info' | 'success' | 'primary'> = {
  critical: 'danger',
  warn: 'warning',
  warning: 'warning',
  info: 'info',
  ok: 'success',
}

const TEXT_MAP: Record<string, string> = {
  critical: '严重',
  warn: '警告',
  warning: '警告',
  info: '提示',
  ok: '正常',
}

const tagType = computed(() => TYPE_MAP[props.level ?? ''] ?? 'primary')
const tagText = computed(() => TEXT_MAP[props.level ?? ''] ?? (props.level ?? '-'))
</script>

<template>
  <el-tag :type="tagType" :size="size ?? 'small'" effect="light">{{ tagText }}</el-tag>
</template>
