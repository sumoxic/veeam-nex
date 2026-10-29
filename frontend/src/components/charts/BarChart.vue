/**
 * 柱状图。
 */
<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsOption } from 'echarts'

echarts.use([BarChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const PALETTE = ['#4d6bfe', '#d98a2b', '#d94f4e', '#3f8f5c', '#7c6cf0', '#3d98a5']

const props = withDefaults(
  defineProps<{
    series: { name: string; data: (number | null)[] }[]
    labels?: string[]
    height?: string
    horizontal?: boolean
  }>(),
  { labels: () => [], height: '260px', horizontal: false },
)

const el = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null

function render() {
  if (!el.value) return
  if (!chart) chart = echarts.init(el.value)
  const catAxis = {
    type: 'category' as const,
    data: props.labels,
    axisLabel: { interval: 0, color: 'rgba(32,33,36,.48)', fontSize: 10.5 },
    axisLine: { lineStyle: { color: 'rgba(32,33,36,.1)' } },
    axisTick: { show: false },
  }
  const valAxis = {
    type: 'value' as const,
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { color: 'rgba(32,33,36,.48)', fontSize: 10.5 },
    splitLine: { lineStyle: { color: 'rgba(32,33,36,.06)', type: 'dashed' as const } },
  }
  const option: EChartsOption = {
    color: PALETTE,
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#ffffff',
      borderColor: 'rgba(32,33,36,.08)',
      borderWidth: 1,
      padding: [8, 12],
      textStyle: { color: '#1e232c', fontSize: 12 },
      extraCssText: 'border-radius:12px;box-shadow:0 12px 32px rgba(18,20,23,.12);',
      axisPointer: { type: 'shadow', shadowStyle: { color: 'rgba(32,33,36,.04)' } },
    },
    legend: {
      data: props.series.map((s) => s.name),
      bottom: 0,
      type: 'scroll',
      icon: 'circle',
      itemWidth: 8,
      itemHeight: 8,
      itemGap: 16,
      textStyle: { color: 'rgba(32,33,36,.62)', fontSize: 11 },
    },
    grid: { left: 44, right: 16, top: 20, bottom: 42, containLabel: true },
    xAxis: props.horizontal ? valAxis : catAxis,
    yAxis: props.horizontal ? catAxis : valAxis,
    series: props.series.map((s, i) => ({
      name: s.name,
      type: 'bar',
      data: s.data,
      barMaxWidth: 30,
      itemStyle: { color: PALETTE[i % PALETTE.length], borderRadius: [6, 6, 0, 0] },
    })),
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

watch(() => [props.series, props.labels], render, { deep: true })
</script>

<template>
  <div ref="el" class="vi-chart" :style="{ height }" />
</template>
