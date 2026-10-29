/**
 * 通用「表格页」骨架：页头（标题 + 工具栏）+ 表格卡片 + 分页。
 *
 * 用法：外层用 DataTablePage 组件，传入 title / total / page / size / loading；
 * toolbar 插槽放工具按钮，默认插槽放完整的 el-table（数据源与列定义都在调用方手里）；
 * 分页由父组件持有状态，本组件只负责双向同步并向上抛事件。
 */
<script setup lang="ts">
import { computed, useSlots } from 'vue'

const props = withDefaults(
  defineProps<{
    /** 页头标题，为空则不显示标题 */
    title?: string
    /** 总条数 */
    total: number
    /** 当前页码（从 1 开始） */
    page: number
    /** 每页条数 */
    size: number
    /** 表格加载态 */
    loading?: boolean
    /** 是否渲染工具栏区域 */
    toolbar?: boolean
  }>(),
  {
    title: '',
    loading: false,
    toolbar: true,
  },
)

const emit = defineEmits<{
  (e: 'update:page', value: number): void
  (e: 'update:size', value: number): void
  (e: 'refresh'): void
}>()

const slots = useSlots()

const pageModel = computed({
  get: () => props.page,
  set: (value: number) => emit('update:page', value),
})

const sizeModel = computed({
  get: () => props.size,
  set: (value: number) => {
    emit('update:size', value)
    // 每页条数变化后当前页多半越界，回到第一页
    emit('update:page', 1)
  },
})
</script>

<template>
  <div class="vi-page">
    <div class="vi-page-header">
      <h2 v-if="title" class="vi-page-title">{{ title }}</h2>
      <div v-if="toolbar" class="vi-toolbar">
        <slot name="toolbar" />
        <el-button :loading="loading" circle title="刷新" @click="emit('refresh')">
          <el-icon><Refresh /></el-icon>
        </el-button>
      </div>
    </div>

    <div class="vi-card">
      <!--
        默认插槽由调用方放入完整的 el-table（数据源、列定义都在调用方手里）；
        这里用一个容器承载 loading 遮罩，同时把 loading 透传给插槽方便自定义。
      -->
      <div v-loading="loading" class="vi-table-host">
        <slot :loading="loading" />
      </div>

      <!-- 父组件提供了 pagination 插槽时，用它替换内置分页 -->
      <slot v-if="slots.pagination" name="pagination" />
      <el-pagination
        v-else
        v-model:current-page="pageModel"
        v-model:page-size="sizeModel"
        :total="total"
        :page-sizes="[20, 50, 100, 200]"
        layout="total, sizes, prev, pager, next, jumper"
        background
        class="vi-pagination"
      />
    </div>
  </div>
</template>

<style scoped>
.vi-table-host {
  min-height: 40px;
}

.vi-pagination {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}
</style>
