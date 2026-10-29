/**
 * 环形占比图：中间叠加大数字，用于任务结果、容量构成等分布。
 */
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import { PieChart } from 'echarts/charts'
import { TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsOption } from 'echarts'

echarts.use([PieChart, TooltipComponent, CanvasRenderer])

const props = withDefaults(
  defineProps<{
    items: { name: string; value: number; color: string }[]
    centerValue?: string | number
    centerLabel?: string
    height?: string
  }>(),
  { height: '180px', centerValue: '', centerLabel: '' },
)

const el = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null

const data = computed(() => {
  const filled = props.items.filter((item) => item.value > 0)
  if (filled.length === 0) {
    return [{ name: '暂无数据', value: 1, itemStyle: { color: '#efeeeb' } }]
  }
  return filled.map((item) => ({
    name: item.name,
    value: item.value,
    itemStyle: { color: item.color },
  }))
})

function render() {
  if (!el.value) return
  if (!chart) chart = echarts.init(el.value)
  const option: EChartsOption = {
    tooltip: {
      trigger: 'item',
      formatter: '{b}<br/>{c} ({d}%)',
      backgroundColor: '#ffffff',
      borderColor: 'rgba(32,33,36,.08)',
      borderWidth: 1,
      padding: [8, 12],
      textStyle: { color: '#1e232c', fontSize: 12 },
      extraCssText: 'border-radius:12px;box-shadow:0 12px 32px rgba(18,20,23,.12);',
    },
    series: [
      {
        type: 'pie',
        radius: ['70%', '90%'],
        center: ['50%', '50%'],
        avoidLabelOverlap: true,
        label: { show: false },
        labelLine: { show: false },
        itemStyle: {
          borderRadius: 10,
          borderColor: '#ffffff',
          borderWidth: 3,
        },
        emphasis: { scale: true, scaleSize: 4 },
        data: data.value,
      },
    ],
  }
  chart.setOption(option, true)
}

function resize() {
  chart?.resize()
}

onMounted(() => {
  render()
  window.addEventListener('resize', resize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resize)
  chart?.dispose()
  chart = null
})

watch(() => props.items, render, { deep: true })
</script>

<template>
  <div class="donut-wrap" :style="{ height }">
    <div ref="el" class="donut-canvas" />
    <div class="donut-center">
      <strong>{{ centerValue }}</strong>
      <span>{{ centerLabel }}</span>
    </div>
  </div>
</template>

<style scoped>
.donut-wrap {
  position: relative;
  width: 100%;
}

.donut-canvas {
  width: 100%;
  height: 100%;
}

.donut-center {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  pointer-events: none;
  gap: 2px;
}

.donut-center strong {
  font-size: 26px;
  font-weight: 650;
  letter-spacing: -0.03em;
  color: var(--vi-text);
  line-height: 1;
}

.donut-center span {
  font-size: 11px;
  color: var(--vi-muted);
  letter-spacing: 0.04em;
}
</style>
