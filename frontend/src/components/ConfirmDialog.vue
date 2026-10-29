/**
 * 两步确认对话框：展示「将要发生什么」，等操作员明确点头才继续。
 *
 * 远程操作、建单这类不可逆动作都走这里：主按钮默认不聚焦、
 * 弹窗点击遮罩不关闭，避免误触。
 */
<script setup lang="ts">
withDefaults(
  defineProps<{
    modelValue: boolean
    title?: string
    message?: string
    /** 将要执行的内容预览，多行文本 */
    previewText?: string
    confirmText?: string
    danger?: boolean
    loading?: boolean
  }>(),
  {
    title: '操作确认',
    message: '',
    previewText: '',
    confirmText: '确认',
    danger: false,
    loading: false,
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  confirm: []
}>()

function close() {
  emit('update:modelValue', false)
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    :title="title"
    width="540px"
    :close-on-click-modal="false"
    :close-on-press-escalate="false"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <p v-if="message" class="vi-confirm-message">{{ message }}</p>

    <pre v-if="previewText" class="vi-mono vi-confirm-preview">{{ previewText }}</pre>

    <slot />

    <template #footer>
      <el-button :disabled="loading" @click="close">取消</el-button>
      <el-button
        :type="danger ? 'danger' : 'primary'"
        :loading="loading"
        @click="emit('confirm')"
      >
        {{ confirmText }}
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.vi-confirm-message {
  margin: 0 0 12px;
  line-height: 1.7;
}

.vi-confirm-preview {
  margin: 0 0 12px;
  padding: 12px;
  max-height: 240px;
  overflow: auto;
  background: #fafbfd;
  border: 1px solid #e8ebf0;
  border-radius: 6px;
  white-space: pre-wrap;
  word-break: break-all;
  line-height: 1.6;
}
</style>
