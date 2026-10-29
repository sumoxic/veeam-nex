/**
 * 折线图 / 面积图。
 *
 * 只注册需要的 ECharts 模块（LineChart、Grid、Tooltip、Legend、CanvasRenderer），
 * 避免把整个 echarts 包进 bundle。
 */
<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import { LineChart, BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, DatasetComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsOption } from 'echarts'

echarts.use([
  LineChart,
  BarChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DatasetComponent,
  CanvasRenderer,
])

const PALETTE = ['#4d6bfe', '#d98a2b', '#d94f4e', '#3f8f5c', '#7c6cf0', '#3d98a5']

const props = withDefaults(
  defineProps<{
    /** 每个序列一条：name + data（x 轴为下标） */
    series: { name: string; data: (number | null)[] }[]
    labels?: string[]
    height?: string
    area?: boolean
    smooth?: boolean
  }>(),
  { labels: () => [], height: '260px', area: true, smooth: true },
)

const el = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null

function gradient(color: string) {
  return new echarts.graphic.LinearGradient(0, 0, 0, 1, [
    { offset: 0, color: `${color}2e` },
    { offset: 1, color: `${color}00` },
  ])
}

function render() {
  if (!el.value) return
  if (!chart) chart = echarts.init(el.value)
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
      axisPointer: { type: 'line', lineStyle: { color: 'rgba(32,33,36,.14)' } },
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
    grid: { left: 44, right: 16, top: 20, bottom: 42 },
    xAxis: {
      type: 'category',
      data: props.labels,
      boundaryGap: false,
      axisLine: { lineStyle: { color: 'rgba(32,33,36,.1)' } },
      axisTick: { show: false },
      axisLabel: { color: 'rgba(32,33,36,.48)', fontSize: 10.5 },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: 'rgba(32,33,36,.48)', fontSize: 10.5 },
      splitLine: { lineStyle: { color: 'rgba(32,33,36,.06)', type: 'dashed' } },
    },
    series: props.series.map((s, i) => {
      const color = PALETTE[i % PALETTE.length]
      return {
        name: s.name,
        type: 'line',
        data: s.data,
        smooth: props.smooth,
        areaStyle: props.area ? { color: gradient(color) } : undefined,
        connectNulls: true,
        symbol: 'circle',
        symbolSize: 6,
        showSymbol: false,
        lineStyle: { width: 2, color },
        itemStyle: { color },
      }
    }),
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
