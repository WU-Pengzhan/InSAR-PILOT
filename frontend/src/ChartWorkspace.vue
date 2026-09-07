<script setup lang="ts">
import { onMounted, onBeforeUnmount, watch, ref } from 'vue'
import * as echarts from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
echarts.use([BarChart, GridComponent, TooltipComponent, CanvasRenderer])
const props = defineProps<{ runs: any[] }>()
const host = ref<HTMLElement>()
let chart: echarts.ECharts | undefined
let resize: ResizeObserver | undefined
function update() {
  const finished = props.runs.filter(r => r.started_at && r.finished_at)
  chart?.setOption({ grid: { left: 180, right: 40, top: 30, bottom: 40 }, tooltip: {},
    xAxis: { type: 'value', name: 'seconds' }, yAxis: { type: 'category', data: finished.map(r => r.step_id) },
    series: [{ type: 'bar', data: finished.map(r => (Date.parse(r.finished_at)-Date.parse(r.started_at))/1000), itemStyle: { color: '#1a8f82', borderRadius: [0, 4, 4, 0] } }] })
}
onMounted(() => { chart = echarts.init(host.value!); update(); resize = new ResizeObserver(() => chart?.resize()); resize.observe(host.value!) })
watch(() => props.runs, update, { deep: true })
onBeforeUnmount(() => { resize?.disconnect(); chart?.dispose() })
</script>
<template><div ref="host" style="height:360px;width:100%"/></template>
