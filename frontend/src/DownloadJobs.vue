<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import AcquisitionDialog from './AcquisitionDialog.vue'
import { productKey, type ProjectTarget, type RemoteProduct } from './acquisition'
import { api } from './api'
import { stateColor } from './status'
const props = defineProps<{ language: string }>()
const t = (en: string, zh: string) => props.language === 'zh' ? zh : en
const filter=ref('all'),textFilter=ref(''),supplementOpen=ref(false),supplementProducts=ref<RemoteProduct[]>([]),supplementProject=ref<ProjectTarget|null>(null)
const jobs = ref<any[]>([]), error = ref(''), loading = ref(true), pending = ref<string[]>([])
const state = (job: any) => job.display_status || job.status
const active = (job: any) => ['RUNNING','QUEUED'].includes(job.status)
const labels: Record<string,string[]> = {not_requested:['Not requested','未请求'],validating:['Validating','正在校验'],unavailable:['Precise EOF not published yet','精密 EOF 暂未发布'],waiting_for_geometry:['Waiting for full SLC geometry','等待完整 SLC 几何'],blocked:['Blocked by preceding file','前序文件未完成'],RUNNING:['Downloading','下载中'],QUEUED:['Queued','等待开始'],PAUSING:['Pausing…','正在暂停…'],PAUSED:['Paused','已暂停'],CANCELLING:['Cancelling…','正在取消…'],CANCELLED:['Cancelled','已取消'],SUCCESS:['Completed','已完成'],FAILED:['Failed','失败'],CONTINUED:['Continued in a new attempt','已建立后续任务'],pending:['Waiting','待下载'],running:['Transferring','传输中'],completed:['Completed','已完成'],downloaded:['Completed','已完成'],skipped:['Skipped / checked locally','已跳过 / 本地检查'],failed:['Failed','失败'],cancelled:['Stopped','已停止']}
const label = (value: string) => labels[value] ? t(labels[value][0],labels[value][1]) : value
const visibleJobs=computed(()=>jobs.value)
const total=ref(0),matched=ref(0),activeCount=ref(0),page=ref(0)
let requestTicket=0,filterTimer:ReturnType<typeof setTimeout>|undefined
watch([filter,textFilter],()=>{page.value=0;clearTimeout(filterTimer);requestTicket++;filterTimer=setTimeout(()=>{void refresh()},250)})
watch(page,()=>{requestTicket++;void refresh()})
function rows(job: any) {
  const items=new Map<string,any>()
  for(const product of job.products||[]) {
    const key=productKey(product)
    for(const role of product.mission==='NISAR'?['RSLC']:['SLC','ORBIT']) {
      const requested=role!=='ORBIT'||job.options?.include_orbits!==false
      items.set(key+':'+role,{product_key:key,scene:{scene_id:product.remote_product_id},product_type:role,status:requested?'pending':'not_requested',mission:product.mission,acquisition_time:product.acquisition_time})
    }
  }
  if(job.options?.include_dem)items.set('COP30:DEM',{product_key:'COP30',scene:{scene_id:'COP30'},product_type:'DEM',status:'waiting_for_geometry'})
  for(const task of [...(job.progress||[]),...(job.results||[])]) {
    const product=job.products?.find((p:any)=>p.remote_product_id===task.scene?.scene_id)
    const key=(task.product_key || (task.product_type==='DEM'?'COP30':product?productKey(product):task.scene?.scene_id))+':'+task.product_type
    items.set(key,{...items.get(key),...task})
  }
  return [...items.entries()].map(([key,value])=>({...value,key}))
}
async function supplement(job:any){
 try{
  supplementProject.value=job.project_id?await api<ProjectTarget>('/projects/'+job.project_id):null
  supplementProducts.value=job.products
  supplementOpen.value=true
 }catch(e){error.value=(e as Error).message}
}
let stopped = false, timer: ReturnType<typeof setTimeout> | undefined
const bytes = (value: number | undefined) => value == null ? '—' : value >= 1024**3 ? `${(value/1024**3).toFixed(2)} GiB` : `${(value/1024**2).toFixed(1)} MiB`
let inFlight: Promise<void> | undefined
let refreshAgain=false
async function refresh() {
  if (inFlight) {refreshAgain=true;return inFlight}
  inFlight = (async () => {
  const ticket=requestTicket
  try {
    const result=await api<any>(`/data/downloads-page?offset=${page.value*10}&limit=10&state=${filter.value}&q=${encodeURIComponent(textFilter.value||'')}`)
    if(stopped||ticket!==requestTicket)return
    jobs.value=result.items;total.value=result.total;matched.value=result.count;activeCount.value=result.active;error.value=''
    if(page.value && !result.items.length)page.value=Math.max(0,Math.ceil(result.count/10)-1)
  } catch(e) {if(!stopped&&ticket===requestTicket)error.value=(e as Error).message} finally {loading.value=false}
  })()
  try {await inFlight} finally {inFlight=undefined;if(refreshAgain&&!stopped){refreshAgain=false;void refresh()}}
}
async function poll() { await refresh(); if (!stopped) timer=setTimeout(poll,activeCount.value?3000:15000) }
async function control(job: any, action: string) {
  if(pending.value.includes(job.job_id))return
  pending.value.push(job.job_id)
  try { await api(`/data/downloads/${job.job_id}/${action}`,{}); await refresh() } catch(e) {error.value=(e as Error).message} finally {pending.value=pending.value.filter(id=>id!==job.job_id)}
}
onMounted(poll)
onBeforeUnmount(() => { stopped=true; clearTimeout(timer);clearTimeout(filterTimer);requestTicket++ })
</script>
<template>
  <section class="download-jobs" data-testid="download-jobs"><div class="section-heading"><h1>{{t('Downloads','下载任务')}} · {{total}}</h1><q-btn flat no-caps icon="refresh" :label="t('Refresh','刷新')" :loading="loading" @click="refresh"/></div>
    <q-banner v-if="error" class="bg-red-1 text-red-10" dense role="alert">{{error}}</q-banner>
    
    <div v-if="loading" class="empty-card">{{t('Loading downloads…','正在加载下载任务…')}}</div>
    <div v-else-if="!total" class="empty-card">{{t('Select SAR products in Data Explorer to start a download. Existing transfers remain accessible here after refresh.','在数据检索中选择影像后开始下载。刷新页面后，仍可从这里查看已有任务。')}}</div>
    <div class="row q-gutter-sm q-mb-md"><q-select outlined dense v-model="filter" emit-value map-options :options="[{label:t('All attempts','全部尝试'),value:'all'},{label:t('Active','进行中'),value:'active'},{label:t('History','历史记录'),value:'history'}]"/><q-input outlined dense v-model="textFilter" clearable :label="t('Find scene, batch or path','查找场景、批次或路径')"/><q-chip>{{activeCount}} {{t('active batches','个进行中批次')}}</q-chip></div>
    <div v-if="total && !matched" class="empty-card">{{t('No matching downloads. Adjust the filter.','没有匹配的下载任务，请调整筛选。')}}</div>
    <q-card v-for="job in visibleJobs" :key="job.job_id" :data-job-id="job.job_id" flat bordered class="q-mb-md"><q-card-section>
      <div class="download-heading"><div><q-badge :color="stateColor(state(job))">{{label(state(job))}}</q-badge><b class="q-ml-sm">{{job.products.length}} {{t('acquisitions','景影像')}}</b></div><div class="download-actions">
        <q-btn v-if="!active(job) && job.products.every((p:any)=>p.mission==='SENTINEL-1')" outline no-caps icon="add_circle_outline" :label="t('Get EOF / DEM','补充 EOF / DEM')" @click="supplement(job)"/>
        <q-btn v-if="active(job) && !job.cancel_requested" outline no-caps icon="pause" :disable="pending.includes(job.job_id)" :label="t('Pause','暂停')" @click="control(job,'pause')"/>
        <q-btn v-if="state(job)==='PAUSED'" color="teal-8" unelevated no-caps icon="play_arrow" :disable="pending.includes(job.job_id)" :label="t('Resume','继续下载')" @click="control(job,'resume')"/>
        <q-btn v-if="['FAILED','CANCELLED'].includes(state(job))" outline no-caps icon="replay" :disable="pending.includes(job.job_id)" :label="t('Retry','重试')" @click="control(job,'retry')"/>
        <q-btn v-if="active(job) || state(job)==='PAUSED'" flat no-caps icon="stop" :disable="pending.includes(job.job_id)" :label="state(job)==='CANCELLING'?t('Retry stop','再次请求停止'):t('Cancel download','取消下载')" @click="control(job,'cancel')"/>
      </div></div>
      <q-expansion-item dense :label="t('Attempt details','任务记录')"><p class="path-text download-meta">{{t('Created','创建时间')}}: {{job.created_at || '—'}} · ID: {{job.job_id}}<br v-if="job.parent_job_id"/><span v-if="job.parent_job_id">{{t('Continues','接续任务')}}: {{job.parent_job_id}}</span><br v-if="job.continued_by"/><span v-if="job.continued_by">{{t('Next attempt','后续任务')}}: {{job.continued_by}}</span></p></q-expansion-item>
      <p class="download-owner"><q-icon :name="job.project_id?'folder_open':'inventory_2'"/> {{job.project_name || (job.project_id?t('Project','工程'):t('Shared library','共享数据仓库'))}}</p>
      <p v-if="job.destination" class="path-text destination-path">{{t('Destination','保存位置')}}: {{job.destination}}</p>
      <q-banner v-if="['PAUSING','CANCELLING'].includes(state(job))" dense class="bg-orange-1 text-orange-10">{{t('Stopping connections; the state changes after the worker exits.','正在停止连接；确认下载进程退出后才更新状态。')}}</q-banner>
      
      <p v-if="job.message" class="path-text">{{job.message}}</p>
      <q-list separator class="download-files"><q-item v-for="task in rows(job)" :key="task.key" class="download-file"><q-item-section>
        <div class="file-heading"><q-badge outline color="teal">{{task.product_type==='ORBIT'?'EOF':task.product_type}}</q-badge><b class="path-text">{{task.scene?.scene_id}}</b><span class="muted">{{task.backend==='library'?t('Referenced existing data','引用已有数据'):label(task.status)}}</span></div>
        <div class="download-meta muted">{{task.mission}} · {{task.acquisition_time || task.scene?.acquisition_time || '—'}}</div>
        <template v-if="task.bytes_total || task.bytes_done || task.status==='running'">
          <q-linear-progress class="q-my-sm" :indeterminate="!task.bytes_total && active(job) && !job.cancel_requested" :value="task.bytes_total ? Math.min(1,task.bytes_done/task.bytes_total) : 0" color="teal"/>
          <div class="download-meta">{{bytes(task.bytes_done)}} / {{bytes(task.bytes_total)}} · {{active(job) && !job.cancel_requested && task.speed_bps>0?`${(task.speed_bps/1024**2).toFixed(1)} MiB/s`:'—'}} · {{t('ETA','预计剩余')}} {{!active(job) || job.cancel_requested || task.eta_seconds==null?'—':`${Math.ceil(task.eta_seconds)} s`}}</div>
        </template>
        <div v-if="task.local_path" class="path-text download-meta">{{task.local_path}}</div><q-expansion-item v-if="task.message" dense :label="t('Details','详情')"><div class="path-text download-meta muted">{{task.message}}</div></q-expansion-item>
      </q-item-section></q-item></q-list>
    </q-card-section></q-card>
    <div v-if="matched>10" class="download-pagination"><q-btn flat :disable="page===0" icon="chevron_left" :aria-label="t('Previous page','上一页')" @click="page--"/><span>{{page+1}} / {{Math.ceil(matched/10)}}</span><q-btn flat :disable="(page+1)*10>=matched" icon="chevron_right" :aria-label="t('Next page','下一页')" @click="page++"/></div>
    <AcquisitionDialog v-model="supplementOpen" :products="supplementProducts" :project="supplementProject" :mode="supplementProject?'add':'download'" :language="language" @committed="refresh"/>
  </section>
</template>
<style scoped>
.download-jobs{max-width:1200px;margin:0 auto}.download-heading,.file-heading{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.download-heading{justify-content:space-between}.download-actions{display:flex;gap:8px;flex-wrap:wrap}.download-meta{font-size:11px!important;line-height:1.7}.download-files{margin-top:16px}.download-file{padding:14px 0}.file-heading b{font-size:12px;flex:1;min-width:180px}.file-heading .muted{font-size:11px}.q-item__section{min-width:0}
</style>
