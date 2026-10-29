/**
 * 仪表盘：用于展示许可实例用量百分比。
 */
<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import { GaugeChart } from 'echarts/charts'
import { TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsOption } from 'echarts'

echarts.use([GaugeChart, TooltipComponent, CanvasRenderer])

const props = withDefaults(
  defineProps<{
    /** 0-100 */
    value?: number | null
    title?: string
    detail?: string
    height?: string
  }>(),
  { value: 0, title: '使用率', height: '220px' },
)

const el = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null

function render() {
  if (!el.value) return
  if (!chart) chart = echarts.init(el.value)
  const value = Math.max(0, Math.min(100, props.value ?? 0))
  const option: EChartsOption = {
    tooltip: {
      formatter: '{b}: {c}%',
      backgroundColor: '#ffffff',
      borderColor: 'rgba(32,33,36,.08)',
      borderWidth: 1,
      padding: [8, 12],
      textStyle: { color: '#1e232c', fontSize: 12 },
      extraCssText: 'border-radius:12px;box-shadow:0 12px 32px rgba(18,20,23,.12);',
    },
    series: [
      {
        type: 'gauge',
        min: 0,
        max: 100,
        startAngle: 210,
        endAngle: -30,
        progress: {
          show: true,
          width: 12,
          roundCap: true,
          itemStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
              { offset: 0, color: '#4d6bfe' },
              { offset: 1, color: '#7c6cf0' },
            ]),
          },
        },
        axisLine: { lineStyle: { width: 12, color: [[1, '#f0efec']] } },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { show: false },
        pointer: { show: false },
        title: {
          show: true,
          offsetCenter: [0, '70%'],
          fontSize: 11,
          color: 'rgba(32,33,36,.55)',
        },
        detail: {
          valueAnimation: true,
          offsetCenter: [0, '32%'],
          fontSize: 24,
          fontWeight: 650,
          formatter: '{value}%',
          color: '#121417',
        },
        data: [{ value: Number(value.toFixed(2)), name: props.title }],
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

watch(() => props.value, render)
</script>

<template>
  <div>
    <div ref="el" class="vi-chart" :style="{ height }" />
    <div v-if="detail" class="vi-gauge-detail vi-muted">{{ detail }}</div>
  </div>
</template>

<style scoped>
.vi-gauge-detail {
  text-align: center;
  font-size: 12px;
  margin-top: -8px;
}
</style>
