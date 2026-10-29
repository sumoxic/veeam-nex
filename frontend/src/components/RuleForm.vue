<script setup lang="ts">
/**
 * 由规则 param_schema 自动生成的参数表单。
 *
 * 后端新增巡检规则时只要在 param_schema 里声明字段，前端无需改动即可渲染出对应控件：
 *   string  → el-input
 *   number  → el-input-number（遵守 min / max）
 *   boolean → el-switch
 *
 * 组件自身不保存状态：值由 modelValue 传入，每次变化整体 emit 一个新对象（不改动 prop）。
 */
import type { RuleParamSchema } from '@/api/types'

const props = defineProps<{
  /** 规则参数定义，来自规则目录的 param_schema */
  schema: RuleParamSchema[]
  /** 当前参数值，键为 param_schema 中的 key */
  modelValue: Record<string, unknown>
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: Record<string, unknown>): void
}>()

function rawValue(key: string): unknown {
  return props.modelValue ? props.modelValue[key] : undefined
}

function stringValue(key: string): string {
  const value = rawValue(key)
  if (value === null || value === undefined) return ''
  return String(value)
}

function numberValue(key: string): number | undefined {
  const value = rawValue(key)
  if (value === null || value === undefined || value === '') return undefined
  const num = Number(value)
  return Number.isNaN(num) ? undefined : num
}

function boolValue(key: string): boolean {
  return Boolean(rawValue(key))
}

/** 写入单个字段：始终产出新对象，空值表示删除该键（回落到规则默认值） */
function update(key: string, value: unknown) {
  const next: Record<string, unknown> = { ...(props.modelValue ?? {}) }
  if (value === undefined || value === null || value === '') {
    delete next[key]
  } else {
    next[key] = value
  }
  emit('update:modelValue', next)
}

/** 暴露给父组件：把表单重置为给定的默认值 */
function reset(defaults: Record<string, unknown>) {
  emit('update:modelValue', { ...defaults })
}

// 各控件的取值回调（放在脚本里写，避免在模板表达式里做类型标注）
function stringHandler(key: string) {
  return (value: string) => update(key, value)
}

function numberHandler(key: string) {
  return (value: number | undefined) => update(key, value)
}

function boolHandler(key: string) {
  return (value: boolean | string | number) => update(key, value)
}

defineExpose({ reset })
</script>

<template>
  <div class="rule-form">
    <template v-for="item in schema || []" :key="item.key">
      <div class="rule-form-item">
        <div class="rule-form-label" :title="item.key">{{ item.label }}</div>
        <div class="rule-form-control">
          <el-input
            v-if="item.type === 'string'"
            :model-value="stringValue(item.key)"
            :placeholder="item.placeholder"
            size="small"
            @update:model-value="stringHandler(item.key)"
          />
          <el-input-number
            v-else-if="item.type === 'number'"
            :model-value="numberValue(item.key)"
            :min="item.min"
            :max="item.max"
            size="small"
            controls-position="right"
            @update:model-value="numberHandler(item.key)"
          />
          <el-switch
            v-else-if="item.type === 'boolean'"
            :model-value="boolValue(item.key)"
            @update:model-value="boolHandler(item.key)"
          />
          <span v-else class="vi-muted">不支持的参数类型：{{ item.type }}</span>
        </div>
      </div>
    </template>
    <div v-if="!schema || schema.length === 0" class="vi-muted rule-form-empty">
      该规则没有可配置参数
    </div>
  </div>
</template>

<style scoped>
.rule-form {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 180px;
}

.rule-form-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.rule-form-label {
  font-size: 12px;
  color: var(--vi-text-muted);
  line-height: 1.2;
}

.rule-form-control {
  display: flex;
  align-items: center;
  gap: 8px;
}

.rule-form-control :deep(.el-input),
.rule-form-control :deep(.el-input-number) {
  width: 100%;
}

.rule-form-empty {
  font-size: 12px;
}
</style>
