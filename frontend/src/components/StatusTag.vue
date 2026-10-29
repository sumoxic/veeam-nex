/**
 * 状态标签：巡检运行 / 发现项 / 操作单 / 告警事件的状态语义映射。
 */
<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  status?: string | null
  kind?: 'run' | 'finding' | 'operation' | 'alert-event'
  size?: 'large' | 'default' | 'small'
}>()

const MAPS: Record<string, Record<string, { type: 'success' | 'danger' | 'warning' | 'info' | 'primary'; text: string }>> = {
  run: {
    success: { type: 'success', text: '成功' },
    failed: { type: 'danger', text: '失败' },
    partial: { type: 'warning', text: '部分成功' },
    running: { type: 'primary', text: '运行中' },
  },
  finding: {
    open: { type: 'danger', text: '待处理' },
    acknowledged: { type: 'warning', text: '已确认' },
    resolved: { type: 'success', text: '已解决' },
  },
  operation: {
    pending: { type: 'warning', text: '待确认' },
    executing: { type: 'primary', text: '执行中' },
    succeeded: { type: 'success', text: '成功' },
    failed: { type: 'danger', text: '失败' },
    expired: { type: 'info', text: '已过期' },
    rejected: { type: 'info', text: '已拒绝' },
  },
  'alert-event': {
    pending: { type: 'warning', text: '待发送' },
    sent: { type: 'success', text: '已发送' },
    failed: { type: 'danger', text: '发送失败' },
    suppressed: { type: 'info', text: '已抑制' },
  },
}

const entry = computed(() => {
  const map = MAPS[props.kind ?? 'run']
  return map[props.status ?? ''] ?? { type: 'primary' as const, text: props.status ?? '-' }
})
</script>

<template>
  <el-tag :type="entry.type" :size="size ?? 'small'" effect="light">{{ entry.text }}</el-tag>
</template>
