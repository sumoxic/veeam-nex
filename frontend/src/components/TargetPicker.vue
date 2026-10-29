/**
 * 通用巡检目标选择器。
 *
 * 内部只关心「id ↔ 名称(地址)」的映射，具体目标对象由调用方另行获取。
 * 新建目标后父组件可以调用 `reload()` 刷新下拉列表。
 */
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { listTargets } from '@/api'
import type { Target } from '@/api/types'

const props = withDefaults(
  defineProps<{
    /** 选中的目标 id */
    modelValue?: number | null
    disabled?: boolean
    placeholder?: string
  }>(),
  {
    modelValue: null,
    disabled: false,
    placeholder: '请选择巡检目标',
  },
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: number | null): void
}>()

const targets = ref<Target[]>([])
const loading = ref(false)

function errMsg(err: unknown): string {
  return err instanceof Error ? err.message : '加载巡检目标失败'
}

/** 重新拉取目标列表（父组件新建目标后可调用） */
async function reload() {
  loading.value = true
  try {
    const res = await listTargets()
    targets.value = res.items ?? []
  } catch (err) {
    ElMessage.error(errMsg(err))
  } finally {
    loading.value = false
  }
}

function handleChange(value: number | null | undefined) {
  // el-select 清空时抛出 undefined，这里统一归一化成 null
  emit('update:modelValue', value === undefined || value === null ? null : Number(value))
}

onMounted(reload)

defineExpose({ reload })
</script>

<template>
  <el-select
    :model-value="props.modelValue ?? undefined"
    :disabled="props.disabled"
    :placeholder="props.placeholder"
    :loading="loading"
    filterable
    clearable
    class="vi-target-picker"
    @update:model-value="handleChange"
  >
    <el-option
      v-for="item in targets"
      :key="item.id"
      :label="`${item.name} (${item.host})`"
      :value="item.id"
    >
      <span>{{ item.name }}</span>
      <span class="vi-target-picker-host vi-muted">{{ item.host }}</span>
    </el-option>
  </el-select>
</template>

<style scoped>
.vi-target-picker {
  width: 100%;
  min-width: 200px;
}

.vi-target-picker-host {
  float: right;
  margin-left: 16px;
}
</style>
