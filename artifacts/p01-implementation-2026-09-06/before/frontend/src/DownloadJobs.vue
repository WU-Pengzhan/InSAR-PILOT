<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { api } from './api'
import { stateColor } from './status'
const props = defineProps<{ language: string }>()
const t = (en: string, zh: string) => props.language === 'zh' ? zh : en
const jobs = ref<any[]>([]), error = ref(''), loading = ref(true), pending = ref<string[]>([])
const state = (job: any) => job.display_status || job.status
const active = (job: any) => ['RUNNING','QUEUED'].includes(job.status)
const labels: Record<string,string[]> = {RUNNING:['Downloading','下载中'],QUEUED:['Queued','等待开始'],PAUSING:['Pausing…','正在暂停…'],PAUSED:['Paused','已暂停'],CANCELLING:['Cancelling…','正在取消…'],CANCELLED:['Cancelled','已取消'],SUCCESS:['Completed','已完成'],FAILED:['Failed','失败'],CONTINUED:['Continued in a new attempt','已建立后续任务'],pending:['Waiting','待下载'],running:['Transferring','传输中'],completed:['Completed','已完成'],downloaded:['Completed','已完成'],skipped:['Skipped / checked locally','已跳过 / 本地检查'],failed:['Failed','失败'],cancelled:['Stopped','已停止']}
const label = (value: string) => labels[value] ? t(labels[value][0],labels[value][1]) : value
function rows(job: any) {
  const items = new Map<string,any>()
  for (const product of job.products || []) for (const type of product.mission==='NISAR'?['RSLC']:['SLC','ORBIT']) items.set(`${product.remote_product_id}:${type}`,{scene:{scene_id:product.remote_product_id},product_type:type,status:'pending',mission:product.mission,acquisition_time:product.acquisition_time})
  for (const task of [...(job.progress || []),...(job.results || [])]) {const key=`${task.scene?.scene_id}:${task.product_type}`; items.set(key,{...items.get(key),...task})}
  return [...items.values()]
}
let stopped = false, timer: ReturnType<typeof setTimeout> | undefined
const bytes = (value: number | undefined) => value == null ? '—' : value >= 1024**3 ? `${(value/1024**3).toFixed(2)} GiB` : `${(value/1024**2).toFixed(1)} MiB`
let inFlight: Promise<void> | undefined
async function refresh() {
  if (inFlight) return inFlight
  inFlight = (async () => {
  try { jobs.value = await api('/data/downloads'); error.value='' } catch(e) { error.value=(e as Error).message } finally {loading.value=false}
  })()
  try {await inFlight} finally {inFlight=undefined}
}
async function poll() { await refresh(); if (!stopped) timer=setTimeout(poll,3000) }
async function control(job: any, action: string) {
  if(pending.value.includes(job.job_id))return
  pending.value.push(job.job_id)
  try { await api(`/data/downloads/${job.job_id}/${action}`,{}); await refresh() } catch(e) {error.value=(e as Error).message} finally {pending.value=pending.value.filter(id=>id!==job.job_id)}
}
onMounted(poll)
onBeforeUnmount(() => { stopped=true; clearTimeout(timer) })
</script>
<template>
  <section class="download-jobs" data-testid="download-jobs"><div class="section-heading"><h1>{{t('Downloads','下载任务')}} · {{jobs.length}}</h1><q-btn flat no-caps icon="refresh" :label="t('Refresh','刷新')" :loading="loading" @click="refresh"/></div>
    <q-banner v-if="error" class="bg-red-1 text-red-10" dense role="alert">{{error}}</q-banner>
    <p>{{t('Pause stops the transfer and keeps partial files. Resume creates a linked attempt using aria2c resume data. Cancel stops this queue and keeps downloaded files.','暂停会停止传输并保留分片；继续时建立关联任务并使用 aria2c 断点续传。取消会结束此队列，保留已下载文件。')}}</p>
    <div v-if="loading" class="empty-card">{{t('Loading downloads…','正在加载下载任务…')}}</div>
    <div v-else-if="!jobs.length" class="empty-card">{{t('Select SAR products in Data Explorer to start a download. Existing transfers remain accessible here after refresh.','在数据检索中选择影像后开始下载。刷新页面后，仍可从这里查看已有任务。')}}</div>
    <q-card v-for="job in jobs" :key="job.job_id" :data-job-id="job.job_id" flat bordered class="q-mb-md"><q-card-section>
      <div class="download-heading"><div><q-badge :color="stateColor(state(job))">{{label(state(job))}}</q-badge><b class="q-ml-sm">{{job.products.length}} {{t('acquisitions','景影像')}}</b></div><div class="download-actions">
        <q-btn v-if="active(job) && !job.cancel_requested" outline no-caps icon="pause" :disable="pending.includes(job.job_id)" :label="t('Pause','暂停')" @click="control(job,'pause')"/>
        <q-btn v-if="state(job)==='PAUSED'" color="teal-8" unelevated no-caps icon="play_arrow" :disable="pending.includes(job.job_id)" :label="t('Resume','继续下载')" @click="control(job,'resume')"/>
        <q-btn v-if="['FAILED','CANCELLED'].includes(state(job))" outline no-caps icon="replay" :disable="pending.includes(job.job_id)" :label="t('Retry','重试')" @click="control(job,'retry')"/>
        <q-btn v-if="active(job) || state(job)==='PAUSED'" flat no-caps icon="stop" :disable="pending.includes(job.job_id)" :label="state(job)==='CANCELLING'?t('Retry stop','再次请求停止'):t('Cancel download','取消下载')" @click="control(job,'cancel')"/>
      </div></div>
      <p class="path-text download-meta">{{t('Created','创建时间')}}: {{job.created_at || '—'}} · ID: {{job.job_id}}<br v-if="job.parent_job_id"/><span v-if="job.parent_job_id">{{t('Continues','接续任务')}}: {{job.parent_job_id}}</span><br v-if="job.continued_by"/><span v-if="job.continued_by">{{t('Next attempt','后续任务')}}: {{job.continued_by}}</span></p>
      <p v-if="job.destination" class="path-text">{{t('Destination','保存位置')}}: {{job.destination}}</p>
      <q-banner v-if="['PAUSING','CANCELLING'].includes(state(job))" dense class="bg-orange-1 text-orange-10">{{t('Stopping connections; the state changes after the worker exits.','正在停止连接；确认下载进程退出后才更新状态。')}}</q-banner>
      <p v-else-if="active(job) && !(job.progress || []).length">{{t('Preparing authentication or waiting for a data lock. Transfer progress has not been reported yet.','正在准备认证或等待数据锁，尚未收到传输进度。')}}</p>
      <p v-if="job.message" class="path-text">{{job.message}}</p>
      <q-list separator class="download-files"><q-item v-for="task in rows(job)" :key="`${task.scene?.scene_id}:${task.product_type}`" class="download-file"><q-item-section>
        <div class="file-heading"><q-badge outline color="teal">{{task.product_type==='ORBIT'?'EOF':task.product_type}}</q-badge><b class="path-text">{{task.scene?.scene_id}}</b><span class="muted">{{label(task.status)}}</span></div>
        <div class="download-meta muted">{{task.mission}} · {{task.acquisition_time || task.scene?.acquisition_time || '—'}}</div>
        <template v-if="task.bytes_total || task.bytes_done || task.status==='running'">
          <q-linear-progress class="q-my-sm" :indeterminate="!task.bytes_total && active(job) && !job.cancel_requested" :value="task.bytes_total ? Math.min(1,task.bytes_done/task.bytes_total) : 0" color="teal"/>
          <div class="download-meta">{{bytes(task.bytes_done)}} / {{bytes(task.bytes_total)}} · {{active(job) && !job.cancel_requested && task.speed_bps>0?`${(task.speed_bps/1024**2).toFixed(1)} MiB/s`:'—'}} · {{t('ETA','预计剩余')}} {{!active(job) || job.cancel_requested || task.eta_seconds==null?'—':`${Math.ceil(task.eta_seconds)} s`}}</div>
        </template>
        <div v-if="task.local_path" class="path-text download-meta">{{task.local_path}}</div><div v-if="task.message" class="path-text download-meta muted">{{task.message}}</div>
      </q-item-section></q-item></q-list>
    </q-card-section></q-card>
  </section>
</template>
<style scoped>
.download-jobs{max-width:1200px;margin:0 auto}.download-heading,.file-heading{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.download-heading{justify-content:space-between}.download-actions{display:flex;gap:8px;flex-wrap:wrap}.download-meta{font-size:11px!important;line-height:1.7}.download-files{margin-top:16px}.download-file{padding:14px 0}.file-heading b{font-size:12px;flex:1;min-width:180px}.file-heading .muted{font-size:11px}.q-item__section{min-width:0}
</style>
