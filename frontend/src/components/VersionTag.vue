/**
 * VBR 版本标签：已探测到构建号时显示实心版本，仅有用户选择时显示待检测态。
 */
<script setup lang="ts">
import { computed } from 'vue'
import { versionLabel, vbrMajor, type VersionPreference } from '@/utils/version'

const props = withDefaults(
  defineProps<{
    build?: string | null
    preference?: VersionPreference | string | null
    size?: 'large' | 'default' | 'small'
  }>(),
  { build: null, preference: null, size: 'small' },
)

const detected = computed(() => vbrMajor(props.build) !== null)
const label = computed(() => versionLabel(props.build, props.preference))
const tone = computed(() => (detected.value ? 'success' : 'info'))
const hint = computed(() => props.build || '尚未探测到构建号')
</script>

<template>
  <el-tag :type="tone" :size="size" effect="light" :title="hint">{{ label }}</el-tag>
</template>
