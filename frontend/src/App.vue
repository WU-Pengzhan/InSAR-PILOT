<script setup lang="ts">
import {windowUrl} from './window-session'
import { computed, defineAsyncComponent, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useQuasar, type QBtn } from 'quasar'
import { api, connectEvents, type NewPipelineRequest } from './api'
import type { AcquisitionResult } from './acquisition'
import { stateColor } from './status'
import { zhLabels } from './labels'
import FilePathField from './FilePathField.vue'
import ProjectEntry from './ProjectEntry.vue'
import ApplicationControl from './ApplicationControl.vue'
import logoMark from './assets/logo-mark.png'
const DataExplorer = defineAsyncComponent(() => import('./DataExplorer.vue'))
const DownloadJobs = defineAsyncComponent(() => import('./DownloadJobs.vue'))
const ComputePanel = defineAsyncComponent(() => import('./ComputePanel.vue'))
import { mergeEvents } from './event-cursor'
const MapWorkspace = defineAsyncComponent(() => import('./MapWorkspace.vue'))
const ChartWorkspace = defineAsyncComponent(() => import('./ChartWorkspace.vue'))

const q = useQuasar()
const language = ref(localStorage.getItem('pilot-language') || 'en')
const t = (en: string, zh: string) => language.value === 'zh' ? zh : en
const profileLabel=(value:string)=>value==='sentinel1_tops'?'Sentinel-1 TOPS':value==='nisar'?'NISAR':t('Unassigned','未指定传感器')
const tr = (en: string) => language.value === 'zh' ? zhLabels[en] || en : en
const dark = ref(localStorage.getItem('pilot-dark') === 'true')
watch(dark, v => { q.dark.set(v); localStorage.setItem('pilot-dark', String(v)) }, { immediate: true })
watch(language, v => localStorage.setItem('pilot-language', v))
const projects = ref<any[]>([]), project = ref<any>(null), compute = ref<any>(null)
const tab = ref('home'), busy = ref(false), error = ref('')
const connectionRequired = ref(false)
const lifecycleView = ref('')
function lifecycleState(value:string) {
  if(value==='stopping')window.dispatchEvent(new Event('pilot-app-exiting'))
  if (['stopping','exited','offline'].includes(value)) {lifecycleView.value=value;disconnect();error.value=''}
  else if(value==='running' && lifecycleView.value) {lifecycleView.value='';void initialize()}
}
const artifacts = ref<any[]>([]), runs = ref<any[]>([]), jobs = ref<any[]>([]), events = ref<any[]>([]), reports = ref<any[]>([])
const selected = ref<any>(null), inspectorTab = ref('properties')
const savedLeft = Number(localStorage.getItem('pilot-explorer-width'))
const left = ref(Number.isFinite(savedLeft) && savedLeft >= 180 ? Math.min(savedLeft, 400) : 230)
watch(left, value => localStorage.setItem('pilot-explorer-width', String(value)), {flush:'sync'})
const inspectorCollapsed = ref(localStorage.getItem('pilot-inspector-collapsed') !== 'false')
const inspectorWidth = ref(Number(localStorage.getItem('pilot-inspector-width')) || 73)
const inspectorAvailable = computed(() => !['home','new','open','downloads'].includes(tab.value) && (!!project.value || tab.value==='explore'))
const inspectorHidden = computed(() => !inspectorAvailable.value || inspectorCollapsed.value)
const inspectorSplit = computed({get: () => inspectorHidden.value ? 100 : inspectorWidth.value, set: (value: number) => { if (!inspectorHidden.value) { inspectorWidth.value=value; localStorage.setItem('pilot-inspector-width', String(value)) } }})
watch(inspectorCollapsed, value => localStorage.setItem('pilot-inspector-collapsed', String(value)))
const inspectorOpenButton = ref<HTMLButtonElement>()
const inspectorCloseButton = ref<QBtn>()
async function toggleInspector(collapsed: boolean) {
  inspectorCollapsed.value=collapsed
  await nextTick()
  if (collapsed) inspectorOpenButton.value?.focus()
  else inspectorCloseButton.value?.$el.focus({preventScroll:true})
}
const expandedNodes = ref(['project','data','run'])
const pipelineId = ref(''), states = ref<any[]>([]), plan = ref<any>(null), files = ref<any[]>([]), filePath = ref('')
const library = ref<any[]>([])
const pipelineSetup = ref(false), pipelineSources = ref<string[]>([])
const postBundle = ref<any>(null)
const importPath = ref(''), importRole = ref('sar')
const templatePath = ref(''), runtimePython = ref(''), parametersText = ref('{}')
const searchSelection = ref<any[]>([]), providerCaps = ref<any[]>([])
let disconnect = () => {}
const pipeline = computed(() => project.value?.pipelines?.[pipelineId.value])
const counts = computed(() => ({ success: states.value.filter(s => s.status === 'SUCCESS').length, total: states.value.length, active: jobs.value.filter(j => ['QUEUED','RUNNING'].includes(j.status)).length }))
const tree = computed(() => project.value ? [{ label: project.value.name, id: 'project', icon: 'folder_open', children: [
  { label: t('Data', '数据'), id: 'data', icon: 'storage', children: artifacts.value.filter(a => !a.created_by_run).map(a => ({ label: a.metadata?.native_product_id || a.type, id: a.artifact_id, icon: 'description' })) },
  { label: t('Processing', '处理'), id: 'run', icon: 'account_tree', children: states.value.map(s => ({ label: tr(s.title), id: s.step_id, icon: s.status === 'SUCCESS' ? 'check_circle' : 'radio_button_unchecked' })) },
  { label: t('Products', '成果'), id: 'products', icon: 'layers' }, { label: 'QC', id: 'qc', icon: 'fact_check' },
] }] : [])

async function act(action: () => Promise<void>) { busy.value = true; error.value = ''; try { await action() } catch (e) { if ((e as {status?: number}).status === 401) { connectionRequired.value=true; disconnect() } else error.value = String((e as Error).message) } finally { busy.value = false } }
const pages = computed(() => [
  { id:'explore', label:t('Search & download','检索与下载') },
  { id:'data', label:t('Data & preparation','数据与准备') },
  { id:'pipeline', label:t('Parameters & generation','参数与生成') },
  { id:'run', label:t('Run','运行') },
  { id:'products', label:t('Products & QC','成果与 QC') },
])
const pageFor = (name: string) => (({ downloads:'explore', jobs:'run', history:'run', events:'run', log:'run', qc:'products', map:'products' } as Record<string,string>)[name] || name)
const activePage = computed(() => pages.value.some(p => p.id === pageFor(tab.value)) ? pageFor(tab.value) : '')
const subpages = computed(() => {
  const groups: Record<string, { id:string; label:string }[]> = {
    explore:[{id:'explore',label:t('Search','检索')},{id:'downloads',label:t('Downloads','下载任务')}],
    run:[{id:'run',label:t('Steps','处理步骤')},{id:'jobs',label:t('Jobs','任务')},{id:'history',label:t('Run history','运行历史')}],
    products:[{id:'products',label:t('Products','成果')},{id:'qc',label:'QC'},{id:'map',label:t('Map','地图')}],
  }
  return groups[activePage.value] || []
})
const publicViews = new Set(['home','new','open','explore','downloads','library','compute','background'])
let projectEpoch=0, openTicket=0, refreshFlight:Promise<void>|undefined
let refreshTimer:ReturnType<typeof setTimeout>|undefined
function openTab(name: string) {
  if (!project.value && !publicViews.has(name)) { tab.value=name==='jobs'?'background':'home'; return }
  tab.value=name
}
function clearProject() {
  projectEpoch++;openTicket++;disconnect();disconnect=()=>{};clearTimeout(refreshTimer);refreshTimer=undefined;refreshFlight=undefined
  project.value=null;selected.value=null;pipelineId.value='';plan.value=null;events.value=[]
  artifacts.value=[];runs.value=[];jobs.value=[];reports.value=[];states.value=[];files.value=[];filePath.value=''
  pipelineSetup.value=false;pipelineSources.value=[];postBundle.value=null;importPath.value='';importRole.value='sar'
  templatePath.value='';runtimePython.value='';parametersText.value='{}';logText.value='';logOffset.value=0
  localStorage.removeItem('pilot-project')
}
function discardEdits():Promise<boolean> {
  if (!importPath.value && !pipelineSetup.value) return Promise.resolve(true)
  return new Promise(resolve=>q.dialog({title:t('Unsaved input','尚未保存的输入'),message:t('Discard the current input and leave this project?','放弃当前尚未保存的输入并离开工程？'),cancel:true,persistent:true}).onOk(()=>resolve(true)).onCancel(()=>resolve(false)))
}
async function closeProject() { if(await discardEdits()){clearProject();tab.value='home';await refreshRecent()} }
async function readProject(id:string, preferred='') {
  const root=`/projects/${id}`
  const [p,a,r,j,e,c]=await Promise.all([api<any>(root),api<any[]>(root+'/artifacts'),api<any[]>(root+'/runs'),api<any[]>(root+'/jobs'),api<any[]>(root+'/events'),api<any[]>(root+'/qc')])
  const pid=p.pipelines[preferred]?preferred:Object.keys(p.pipelines)[0]||''
  const steps=pid?await api<any[]>(`${root}/pipelines/${pid}/states`):[]
  return {p,a,r,j,e,c,pid,steps}
}
function applyProject(d:Awaited<ReturnType<typeof readProject>>) {
  project.value=d.p;artifacts.value=d.a;runs.value=d.r;jobs.value=d.j;reports.value=d.c
  events.value=mergeEvents(events.value,d.e);pipelineId.value=d.pid;states.value=d.steps
}
async function refresh() {
  if (!project.value) return
  if(refreshFlight)return refreshFlight
  const epoch=projectEpoch,id=project.value.project_id,preferred=pipelineId.value
  const pending=(async()=>{const data=await readProject(id,preferred);if(epoch===projectEpoch && project.value?.project_id===id)applyProject(data)})()
  refreshFlight=pending
  try {await pending} finally {if(refreshFlight===pending)refreshFlight=undefined}
}
async function selectProject(p:any,ticket=++openTicket) {
  const startingTab=tab.value
  const data=await readProject(p.project_id)
  if(ticket!==openTicket)return
  clearProject();applyProject(data)
  const epoch=projectEpoch
  if(tab.value===startingTab)openTab('data')
  disconnect=connectEvents(p.project_id,events.value.at(-1)?.sequence||0,rows=>{
    if(epoch!==projectEpoch)return
    events.value=mergeEvents(events.value,rows)
    if(!rows.length||refreshTimer)return
    refreshTimer=setTimeout(()=>{refreshTimer=undefined;void refresh().catch(e=>{if(epoch===projectEpoch)error.value=e.message})},500)
  },()=>{if(epoch===projectEpoch){connectionRequired.value=true;disconnect()}})
}
async function refreshRecent(){projects.value=await api('/projects')}
function selectObject(id: string) {
  const a = artifacts.value.find(a => a.artifact_id === id)
  const s = states.value.find(s => s.step_id === id)
  if (a) { selected.value=a; openTab('products') }
  else if (s) { selected.value=s; openTab('run') }
  else openTab(id)
}
async function projectOpened(p:any) {
  await act(async()=>{projects.value=await api('/projects');await selectProject(p)})
}
async function openRecent(p:any) {
  if(!(await discardEdits()))return
  const ticket=++openTicket
  await act(async()=>{const opened=await api('/projects/open',{path:p.project_file||p.path});await refreshRecent();if(ticket===openTicket)await selectProject(opened,ticket)})
}
async function importData() { await act(async () => {
  await api(`/projects/${project.value.project_id}/sources`, { paths: importPath.value.split('\n').map(p=>p.trim()).filter(Boolean), role: importRole.value })
  await refresh(); importPath.value=''
}) }
async function bindDataset() { await act(async () => {
  const sources=artifacts.value.filter(a => !a.created_by_run && ['sentinel1_tops','nisar'].includes(a.mission))
  if (!sources.length) throw Error('Import processing SLC/RSLC files first.')
  if (new Set(sources.map(a=>a.mission)).size !== 1) throw Error('Select a single mission for a processing project.')
  await api(`/projects/${project.value.project_id}/datasets`, { artifact_ids: sources.map(a=>a.artifact_id), profile: sources[0].mission, expected_revision:project.value.revision }); await refresh()
}) }
async function createPipeline() { await act(async () => {
  const p=project.value, source=artifacts.value.filter(a=>!a.created_by_run)
  const sar=source.filter(a=>a.assets.length && ['Sentinel1SLC','NisarRSLC'].includes(a.type) && (!pipelineSources.value.length || pipelineSources.value.includes(a.artifact_id)))
  const dem=source.filter(a=>a.type==='DEM')
  if (!runtimePython.value) throw Error('Choose the processor Python executable.')
  if (dem.length !== 1) throw Error('Import one prepared DEM for this pipeline.')
  const params=JSON.parse(parametersText.value)
  let inputs: Record<string,string[]>
  if (p.profile==='nisar') {
    if (sar.length!==2) throw Error('This pipeline requires two RSLC inputs.')
    inputs={reference:[sar[0].artifact_id],secondary:[sar[1].artifact_id],dem:[dem[0].artifact_id]}
    Object.assign(params,{template_path:templatePath.value,frequency:params.frequency || 'A',polarization:params.polarization || 'HH',product_type:params.product_type || 'GUNW'})
  } else inputs={slc:sar.map(a=>a.artifact_id),dem:[dem[0].artifact_id],orbit:source.filter(a=>a.type==='OrbitEOF').map(a=>a.artifact_id)}
  const request:NewPipelineRequest={ profile:p.profile,inputs,parameters:params,environment:{python_executable:runtimePython.value},expected_revision:p.revision };const result=await api(`/projects/${p.project_id}/pipelines`,request)
  pipelineId.value=result.pipeline_id; pipelineSetup.value=false; await refresh()
}) }
async function preview(through?: string) { await act(async () => { plan.value=await api(`/projects/${project.value.project_id}/pipelines/${pipelineId.value}/plans`,{through_step:through || null}); openTab('pipeline') }) }
async function submit() { await act(async () => { await api(`/projects/${project.value.project_id}/plans/${plan.value.plan_id}/submit`,{}); plan.value=null; await refresh(); openTab('run') }) }
async function acquisitionCommitted(result: AcquisitionResult) {
 await act(async()=>{projects.value=await api('/projects');if(result.project)await selectProject(result.project);else await refresh();openTab(result.job?'downloads':'data')})
}
async function downloadOnly() { await act(async () => { await api('/data/downloads',{product_ids:searchSelection.value.map(p=>p.remote_product_id)}); openTab('downloads') }) }
async function browse(relative='') { files.value=await api(`/projects/${project.value.project_id}/files?relative=${encodeURIComponent(relative)}`); filePath.value=relative; openTab('files') }
const logText = ref(''), logOffset=ref(0), logStream=ref('stdout')
async function readLog(reset=true) { if(reset){logText.value='';logOffset.value=0} const r=await api(`/projects/${project.value.project_id}/runs/${selected.value.run_id}/logs/${logStream.value}?offset=${logOffset.value}`); logText.value+=r.text;logOffset.value=r.next_offset;openTab('log') }
async function openLibrary() { library.value=await api('/data/library');openTab('library') }
onBeforeUnmount(()=>{disconnect();clearTimeout(refreshTimer);clearInterval(recentTimer)})
async function initialize() {
  await act(async () => {
    await api('/health')
    connectionRequired.value = false
    ;[projects.value, compute.value, providerCaps.value] = await Promise.all([api('/projects'), api('/compute'), api('/data/capabilities')])
    localStorage.removeItem('pilot-project')
  })
}
let recentTimer:ReturnType<typeof setInterval>|undefined
onMounted(()=>{void initialize();recentTimer=setInterval(()=>{if(['home','background'].includes(tab.value) && !connectionRequired.value)void refreshRecent().catch(()=>{})},15000)})
</script>

<template>
<q-layout view="hHh lpR fFf">
  <q-header class="topbar"><q-toolbar>
    <div class="brand" @click="openTab('home')"><img :src="logoMark" alt="InSAR-PILOT logo" class="brand-logo"/><b>InSAR<span>-PILOT</span></b></div>
    <q-separator vertical inset class="q-mx-lg"/><span class="project-name" :title="project?.path || ''">{{ project?.name || t('No project open','未打开工程') }}</span>
    <q-btn v-if="project" flat dense icon="close" :aria-label="t('Close project','关闭工程')" @click="closeProject"/><q-space/><q-chip dense square color="teal-1" text-color="teal-9" icon="memory" data-testid="compute-entry" @click="openTab('compute')" clickable>{{ t('Environment','运行环境') }}</q-chip>
    <q-btn flat dense icon="download" :label="t('Downloads','下载')" @click="openTab('downloads')"/>
    <q-btn flat dense icon="travel_explore" :label="t('Explore','检索')" @click="openTab('explore')"/>
    <q-btn flat dense icon="translate" @click="language=language==='en'?'zh':'en'" aria-label="Change language"/>
    <q-btn flat dense :icon="dark?'light_mode':'dark_mode'" @click="dark=!dark" aria-label="Toggle theme"/>
    <ApplicationControl v-if="compute && !connectionRequired" :language="language" @state="lifecycleState" @jobs="openTab('jobs')"/>
  </q-toolbar></q-header>
  <q-page-container><q-page class="workbench">
    <q-banner v-if="error && !lifecycleView" class="bg-red-1 text-red-10 error-banner" role="alert" dense><template #avatar><q-icon name="error_outline"/></template>{{error}}<template #action><q-btn flat icon="close" @click="error=''"/></template></q-banner>
    <q-linear-progress v-if="busy" indeterminate class="global-progress"/>
    <section v-if="lifecycleView" class="application-exit-screen" data-testid="application-exit-screen">
      <q-icon :name="lifecycleView==='exited'?'power_settings_new':lifecycleView==='stopping'?'hourglass_top':'cloud_off'" size="48px"/>
      <h1>{{lifecycleView==='exited'?t('Exit complete','退出完成'):lifecycleView==='stopping'?t('Exiting the application…','正在退出应用…'):t('Backend connection lost','后台连接已断开')}}</h1>
      <p>{{lifecycleView==='exited'?t('The backend has stopped. Start the application in your terminal before reconnecting; refreshing cannot start it.','后台服务已停止。重新使用时需在终端启动软件，仅刷新页面不能启动后台。'):lifecycleView==='stopping'?t('No active tasks remain. Waiting for the local service to close.','已确认没有运行中的任务，正在等待本机服务退出。'):t('A lost connection does not confirm the application has exited. Check its status in your Linux terminal.','连接断开不代表软件已经退出，请在 Linux 终端查询后台状态。')}}</p>
      <p>{{t('Check status:','查询状态：')}} <code>insar-pilot-web --status</code></p>
      <p>{{t('Start again:','重新启动：')}} <code>insar-pilot-web</code></p>
    </section>
    <section v-else-if="connectionRequired" class="q-pa-xl" data-testid="session-required">
      <h1>{{t('Local connection unavailable','本机连接未建立')}}</h1>
      <p>{{t('Any browser can open this local address while the backend is running. No launcher sign-in is required.','后台运行时，任意浏览器都可直接打开此本机地址，无需通过启动器登录。')}}</p>
      <p>{{t('Check that cookies are allowed for this address and that a browser extension is not blocking local requests, then retry.','请检查是否允许此地址使用 Cookie，以及浏览器扩展是否拦截本机请求，然后重试。')}}</p>
      <p>{{t('If you exited the application, start the backend again:','如果已退出应用，请先重新启动后台：')}} <code>insar-pilot-web --no-browser</code></p>
      <q-btn no-caps color="teal" :loading="busy" :label="t('Check connection again','重新检查连接')" @click="initialize"/>
    </section>
    <q-splitter v-else v-model="left" class="shell-splitter explorer-splitter" unit="px" emit-immediately :limits="[180,400]" :separator-aria-label="t('Resize project explorer','调整工程栏宽度')">
      <template #before><aside class="explorer">
        <div class="explorer-heading"><span class="eyebrow">{{t('PROJECT EXPLORER','工程浏览器')}}</span><q-btn flat dense icon="home" :aria-label="t('Home','首页')" @click="openTab('home')"/></div>
        <div v-if="!project" class="empty-tree"><q-icon name="folder_open" size="38px"/><p>{{t('Open a project to explore its data and processing history.','打开工程以查看数据和处理历史。')}}</p><q-btn outline no-caps :label="t('New project','新建工程')" @click="openTab('new')"/></div>
        <div v-else class="project-tree-scroll" tabindex="0" :aria-label="t('Project tree · scroll to read full names','工程树 · 可滚动查看完整名称')"><q-tree :nodes="tree" node-key="id" v-model:expanded="expandedNodes" @update:selected="selectObject" :selected="selected?.artifact_id || selected?.step_id || tab"><template #default-header="prop"><span class="tree-node-label" :title="prop.node.label">{{prop.node.label}}</span></template></q-tree></div>
        <div class="explorer-bottom"><q-btn flat no-caps icon="download" :label="t('Downloads','下载任务')" @click="openTab('downloads')"/><q-btn flat no-caps icon="folder" :label="t('Files view','文件视图')" :disable="!project" @click="act(()=>browse())"/><q-btn flat no-caps icon="inventory_2" :label="t('Data Library','数据仓库')" @click="act(openLibrary)"/></div>
      </aside></template>
      <template #after><div class="inspector-layout"><q-splitter v-model="inspectorSplit" class="shell-splitter inspector-splitter" :class="{'inspector-collapsed': inspectorHidden}" :limits="inspectorHidden ? [100,100] : [55,85]" :disable="inspectorHidden">
        <template #before><main class="workspace">
          <q-tabs :model-value="activePage" @update:model-value="openTab" dense no-caps align="left" class="workspace-tabs" data-testid="primary-pages" :aria-label="t('Workflow pages','工作流程页面')" active-color="teal-8" indicator-color="teal"><q-tab v-for="(page,i) in pages" :key="page.id" :name="page.id" :label="(i+1)+' '+page.label" :disable="page.id!=='explore' && !project"/></q-tabs>
          <nav v-if="subpages.length" class="workspace-subnav" :aria-label="t('Page views','页内视图')"><q-btn v-for="view in subpages" :key="view.id" flat dense no-caps :label="view.label" :color="tab===view.id?'teal-8':undefined" :aria-current="tab===view.id?'page':undefined" @click="openTab(view.id)"/></nav>
          <div class="workspace-content">
            <section v-if="tab==='home'" class="home">
              <div class="eyebrow">{{t('SAR / InSAR WORKBENCH','SAR / InSAR 工作台')}}</div><h1>{{t('Choose your project','选择工程，开始工作')}}</h1>
              <p class="lede">{{t('Open an existing project, create a new one, or start with a data search.','打开已有工程、创建新工程，或先检索和下载数据。')}}</p>
              <div class="home-actions"><q-btn unelevated color="teal-8" no-caps icon="add" :label="t('New project','新建工程')" @click="openTab('new')"/><q-btn outline no-caps icon="folder_open" :label="t('Open project','打开工程')" @click="openTab('open')"/><q-btn flat no-caps icon="travel_explore" :label="t('Explore SAR data','检索 SAR 数据')" @click="openTab('explore')"/></div>
              <div class="section-heading"><h2>{{t('Recent projects','最近工程')}}</h2><span>{{projects.length}}</span></div>
              <div v-if="!projects.length" class="empty-card">{{t('Your project history starts here. Create a project or begin with a data search.','创建工程或检索数据，开始你的工作。')}}</div>
              <button v-for="p in projects" :key="p.project_id" class="project-card" @click="openRecent(p)" :disabled="!p.available"><q-icon name="folder_open" size="26px" color="teal"/><div><b>{{p.name}}</b><small :title="p.project_file || p.path">{{p.project_file || p.path}}</small><small>{{p.opened_at ? new Date(p.opened_at).toLocaleString(language) : ''}} · {{p.available?(p.datasets?.length?t('Data selected','已选择数据'):t('No data selected','尚未选择数据')):t('Unavailable','不可用')}} · {{p.active_jobs ?? '—'}} {{t('running / queued','运行 / 等待')}}</small></div><q-badge outline color="teal">{{profileLabel(p.profile)}}</q-badge><q-icon name="chevron_right"/></button>
            </section>
            <section v-else-if="tab==='background'"><h1>{{t('Background activity','后台任务')}}</h1><p class="muted">{{t('Open the owning project to inspect processing. Downloads remain available globally.','打开所属工程以查看处理任务；下载任务可直接管理。')}}</p><q-btn outline icon="download" :label="t('Downloads','下载任务')" @click="openTab('downloads')"/><q-list separator><q-item v-for="p in projects" :key="p.project_id"><q-item-section><q-item-label>{{p.name}}</q-item-label><q-item-label caption>{{p.active_jobs ?? '—'}} {{t('processing jobs','个处理任务')}}</q-item-label></q-item-section><q-item-section side><q-btn flat :disable="!p.available" :label="t('Open project','打开工程')" @click="openRecent(p)"/></q-item-section></q-item></q-list></section>
            <ProjectEntry v-else-if="tab==='new'||tab==='open'" :key="tab" :mode="tab" :language="language" @opened="projectOpened"/>
            <DataExplorer v-else-if="tab==='explore'" v-model:selection="searchSelection" :language="language" :project="project" :project-available="!!project" @inspect="selected=$event;inspectorCollapsed=false" @committed="acquisitionCommitted"/>
            <section v-else-if="tab==='data'" class="form-section"><h1>{{t('Project data','工程数据')}}</h1><p class="muted">{{t('Manage the inputs for this project. Existing files can be referenced.','管理本工程的输入数据，也可以引用已有文件。')}}</p><q-select outlined v-model="importRole" :options="['sar','dem','orbit']" :label="tr('Input role')"/><FilePathField v-model="importPath" mode="any" multiple :language="language" :label="t('Input files or SAFE folders · one per line','输入文件或 SAFE 文件夹 · 每行一个')"/><div class="row q-gutter-sm"><q-btn color="teal" no-caps :label="tr('Import references')" @click="importData"/><q-btn outline no-caps :label="tr('Attach processing dataset')" @click="bindDataset"/></div><q-list bordered separator class="q-mt-lg"><q-item v-for="a in artifacts.filter(a=>!a.created_by_run)" :key="a.artifact_id" clickable @click="selected=a"><q-item-section><q-item-label>{{a.type}}</q-item-label><q-item-label caption class="path-text">{{a.assets[0]?.uri || a.metadata.remote_product_id}}</q-item-label></q-item-section><q-item-section side>{{a.mission}}</q-item-section></q-item></q-list></section>
            <section v-else-if="(tab==='pipeline' || tab==='run')" class="pipeline-view">
              <div class="section-heading"><div><div class="eyebrow">{{project?.profile || 'NO PROJECT'}}</div><h1>{{tab==='run'?t('Run','运行'):t('Parameters & generation','参数与生成')}}</h1></div><q-btn v-if="pipeline && tab==='pipeline'" flat no-caps :label="tr('Add pipeline')" @click="pipelineSetup=true"/><q-btn v-if="pipeline && !pipelineSetup && tab==='pipeline'" unelevated color="teal-8" no-caps icon="play_arrow" :label="tr('Plan execution')" @click="preview()"/></div>
              <template v-if="pipeline && (!pipelineSetup || tab==='run')"><div class="pipeline-summary"><span>{{counts.success}} / {{counts.total}} {{t('current','当前有效')}}</span><span>{{runs.length}} {{t('recorded runs','次运行记录')}}</span><span>{{artifacts.filter(a=>a.created_by_run).length}} {{t('artifacts','项成果')}}</span></div>
              <q-select v-if="Object.keys(project.pipelines).length>1" outlined dense v-model="pipelineId" :options="Object.keys(project.pipelines)" :label="tr('Pipeline')" @update:model-value="refresh"/>
              <button v-for="(s,i) in (tab==='run'?states:[])" :key="s.step_id" class="step-row" :class="{chosen:selected?.step_id===s.step_id}" @click="selected=s"><span class="step-number">{{String(i+1).padStart(2,'0')}}</span><div class="step-label"><b>{{tr(s.title)}}</b><small v-if="s.reasons.length">{{s.reasons.join(' · ')}}</small></div><q-badge :color="stateColor(s.status)" :label="s.status"/><q-icon name="chevron_right"/></button>
              <q-btn v-if="tab==='pipeline'" flat no-caps :label="t('Open run monitor','查看运行步骤')" @click="openTab('run')"/><div v-if="plan && tab==='pipeline'" class="plan-card"><h2>{{t('Review execution plan','核对执行计划')}}</h2><p>{{plan.steps.length}} steps · revision {{plan.revision}} · new isolated workspace</p><p>{{t('Required upstream steps are included.','已包含必要的上游重算步骤。')}}</p><code class="path-text">{{plan.working_directory}}</code><ol><li v-for="s in plan.steps" :key="s.step_id">{{tr(s.title)}}</li></ol><q-expansion-item :label="t('Frozen input references','冻结的输入引用')"><pre class="metadata">{{JSON.stringify(plan.exact_inputs,null,2)}}</pre></q-expansion-item><q-btn color="teal" unelevated no-caps :label="tr('Submit this plan')" @click="submit" :loading="busy"/><q-btn flat no-caps :label="tr('Dismiss')" @click="plan=null"/></div>
              </template>
              <template v-else-if="tab==='run'"><div class="empty-card">{{t('Configure a pipeline to view its steps.','配置处理方案后查看运行步骤。')}}</div><q-btn flat no-caps :label="t('Parameters & generation','参数与生成')" @click="openTab('pipeline')"/></template><template v-else><div class="empty-card">{{t('Attach a processing dataset, then configure its mission-specific pipeline.','先绑定处理数据集，再配置对应任务的流水线。')}}</div><div v-if="project?.profile_locked" class="form-section"><q-select outlined multiple v-model="pipelineSources" :options="artifacts.filter(a=>a.assets.length && ['Sentinel1SLC','NisarRSLC'].includes(a.type)).map(a=>({label:a.metadata.native_product_id || a.assets[0].uri, value:a.artifact_id}))" emit-value map-options :label="tr('Processing acquisitions · reference first')"/><FilePathField v-model="runtimePython" mode="file" :language="language" :label="tr('Processor Python executable')"/><FilePathField v-if="project.profile==='nisar'" v-model="templatePath" mode="file" :language="language" :label="tr('Validated ISCE3 runconfig template')"/><q-input outlined type="textarea" v-model="parametersText" :label="tr('Scientific parameters · JSON')"/><q-btn no-caps color="teal" :label="tr('Create pipeline')" @click="createPipeline"/></div><q-btn v-else flat color="teal" no-caps :label="tr('Go to Data')" @click="openTab('data')"/></template>
            </section>
            <section v-else-if="tab==='products'"><div class="section-heading"><h1>{{t('Products','成果')}}</h1><q-btn flat icon="map" :label="tr('Map')" no-caps @click="openTab('map')"/></div><div class="product-grid"><button v-for="a in artifacts.filter(a=>a.created_by_run)" :key="a.artifact_id" class="artifact-card" @click="selected=a"><q-icon name="layers" size="30px" color="teal"/><b>{{a.type}}</b><small>{{a.spatial?.grid_kind || 'Scientific asset'}}</small><code>{{a.artifact_id.slice(0,12)}}</code></button></div><div v-if="selected?.metadata?.phase_dataset" class="image-view"><img :src="windowUrl(`/api/v1/projects/${project.project_id}/artifacts/${selected.artifact_id}/preview.png`)" :alt="selected.type"/><small>Display sample · scientific values are preserved in the source artifact</small></div></section>
            <section v-else-if="tab==='map'" class="full-map"><MapWorkspace :project-id="project?.project_id" :artifact="selected?.artifact_id?selected:undefined"/></section>
            <section v-else-if="tab==='qc'"><h1>{{tr('Quality control')}}</h1><p class="muted">Structural gates and scientific observations are evaluated separately.</p><div v-if="!reports.length" class="empty-card">QC reports appear when a run has evidence to evaluate.</div><q-card v-for="r in reports" :key="r.report_id" flat bordered class="q-mb-md"><q-card-section><b>Report {{r.report_id.slice(0,8)}}</b><small class="block muted">Policy {{r.policy_version}} · {{r.created_at}}</small></q-card-section><q-list separator><q-item v-for="(c,i) in r.checks" :key="i"><q-item-section><q-item-label class="path-text">{{c.check.metric_id}}</q-item-label><q-item-label caption>{{c.explanation}}</q-item-label></q-item-section><q-item-section side>{{c.metric?.value ?? '—'}} {{c.metric?.unit}}</q-item-section><q-item-section side><q-badge :color="stateColor(c.status)">{{c.status}}</q-badge></q-item-section></q-item></q-list></q-card></section>
            <section v-else-if="tab==='history'"><h1>{{tr('Run history')}}</h1><ChartWorkspace :runs="runs"/><q-list bordered separator><q-item v-for="r in [...runs].reverse()" :key="r.run_id" clickable @click="selected=r"><q-item-section><q-item-label>{{r.step_id}}</q-item-label><q-item-label caption>{{r.run_id}} · {{r.created_at}}</q-item-label></q-item-section><q-item-section side><q-badge :color="stateColor(r.status)">{{r.status}}</q-badge></q-item-section></q-item></q-list></section>
            <section v-else-if="tab==='events'"><h1>{{tr('Structured events')}}</h1><div v-for="e in [...events].reverse()" :key="e.event_id" class="event-row"><time>{{new Date(e.created_at).toLocaleTimeString()}}</time><b>{{e.event_type}}</b><small>{{e.payload.status || e.payload.step_id || e.payload.run_id || ''}}</small></div></section>
            <section v-else-if="tab==='log'"><div class="section-heading"><h1>{{tr('Full log')}}</h1><q-select dense v-model="logStream" :options="['stdout','stderr']" @update:model-value="readLog(true)"/><q-btn flat no-caps :label="tr('Load more')" @click="readLog(false)"/></div><pre class="full-log">{{logText || 'No output in this stream.'}}</pre></section>
            <section v-else-if="tab==='files'"><h1>{{tr('Files')}}</h1><q-breadcrumbs class="q-mb-md"><q-breadcrumbs-el :label="tr('Project')" @click="act(()=>browse())"/><q-breadcrumbs-el :label="filePath"/></q-breadcrumbs><q-list bordered separator><q-item v-for="f in files" :key="f.relative" :clickable="f.directory" @click="f.directory && act(()=>browse(f.relative))"><q-item-section avatar><q-icon :name="f.directory?'folder':'description'"/></q-item-section><q-item-section>{{f.name}}</q-item-section><q-item-section side>{{f.size === null?'':f.size+' bytes'}}</q-item-section></q-item></q-list></section>
            <section v-else-if="tab==='library'"><h1>{{tr('Data Library')}}</h1><p>Shared references across projects. Raw inputs are retained.</p><q-list bordered separator><q-item v-for="a in library" :key="a.asset_id"><q-item-section><q-item-label class="path-text">{{a.path}}</q-item-label><q-item-label caption>{{(a.snapshot.size/1024**3).toFixed(2)}} GiB · {{a.fingerprint_kind}}</q-item-label></q-item-section><q-item-section side><q-btn v-if="project" flat no-caps :label="tr('Add to project')" @click="act(async()=>{await api(`/projects/${project.project_id}/sources`,{paths:[a.path],role:'sar'});await refresh();openTab('data')})"/></q-item-section></q-item></q-list></section>
            <section v-else-if="tab==='jobs'"><DownloadJobs :language="language"/><h1 class="q-mt-xl">{{t('Jobs','任务')}}</h1><q-list bordered separator><q-item v-for="j in jobs" :key="j.job_id"><q-item-section><q-item-label>{{j.run_id}}</q-item-label><q-item-label caption>{{j.heartbeat || j.status}}</q-item-label></q-item-section><q-item-section side><q-badge :color="stateColor(j.status)">{{j.status}}</q-badge><q-btn v-if="['QUEUED','RUNNING'].includes(j.status)" flat no-caps :label="t('Cancel','取消')" @click="act(async()=>{await api('/projects/'+project.project_id+'/jobs/'+j.job_id+'/cancel',{});await refresh()})"/></q-item-section></q-item></q-list></section>
            <DownloadJobs v-else-if="tab==='downloads'" :language="language"/>
            <ComputePanel v-else-if="tab==='compute'" :language="language" :cpu-count="compute?.cpu_count" :current-python="pipeline?.environment?.python_executable" :current-processor="project?.profile==='nisar'?'isce3':'isce2'"/>
            <section v-else-if="tab==='post'"><div class="eyebrow">POST-PROCESSING</div><q-btn flat no-caps :label="tr('Inspect available inputs')" @click="act(async()=>{postBundle=await api('/projects/'+project.project_id+'/postprocessing-inputs')})"/><pre v-if="postBundle" class="metadata">{{JSON.stringify(postBundle,null,2)}}</pre><h1>Ready for what comes next.</h1><p>Standard artifacts, pair metadata and provenance form the input contract for future time-series workflows.</p><q-list bordered><q-item v-for="name in ['SBAS','Phase linking','Atmospheric correction','Time-series inversion','Velocity']" :key="name"><q-item-section>{{name}}</q-item-section><q-item-section side>Not implemented</q-item-section></q-item></q-list></section>
            <section v-else-if="tab==='project'"><h1>{{project?.name}}</h1><pre class="metadata">{{JSON.stringify(project,null,2)}}</pre></section>
          </div>
        </main></template>
        <template #after><aside id="properties-panel" v-show="!inspectorHidden" class="inspector"><div class="inspector-heading"><div class="eyebrow">{{tr('INSPECTOR')}}</div><q-btn ref="inspectorCloseButton" flat dense icon="chevron_right" :aria-label="t('Hide properties panel','收起属性面板')" aria-controls="properties-panel" :aria-expanded="true" @click="toggleInspector(true)"/></div><h3>{{selected?.type || selected?.title || selected?.step_id || t('Object details','对象详情')}}</h3><q-tabs v-model="inspectorTab" dense no-caps align="left" active-color="teal"><q-tab name="properties" :label="tr('Properties')"/><q-tab name="qc" :label="tr('QC')"/><q-tab name="history" :label="tr('History')"/></q-tabs>
          <div v-if="!selected" class="inspector-empty"><q-icon name="touch_app" size="28px"/><p>{{t('Select a step, run or artifact to inspect its properties and provenance.','选择步骤、运行或成果，查看属性与来源。')}}</p></div>
          <template v-else><div class="q-pa-md"><q-badge v-if="selected.status" :color="stateColor(selected.status)" class="q-mb-md">{{selected.status}}</q-badge>
            <template v-if="inspectorTab==='properties'"><dl><template v-for="key in ['type','mission','step_id','run_id','created_by_run','created_at','finished_at','exit_code','failure_kind','active_run_id']" :key="key"><template v-if="selected[key]!==undefined && selected[key]!==null"><dt>{{key.replaceAll('_',' ')}}</dt><dd>{{selected[key]}}</dd></template></template></dl><q-expansion-item :label="tr('Metadata and provenance')" dense><pre class="metadata">{{JSON.stringify(selected,null,2)}}</pre></q-expansion-item></template>
            <template v-if="inspectorTab==='qc'"><p>{{selected.qc_gate_passed===undefined?'Open QC for structured evidence.':selected.qc_gate_passed?'Required checks passed.':'Required checks did not pass.'}}</p><q-btn flat no-caps :label="tr('Open QC workspace')" @click="openTab('qc')"/></template>
            <template v-if="inspectorTab==='history'"><q-list><q-item v-for="r in runs.filter(r=>r.step_id===selected.step_id || r.run_id===selected.created_by_run)" :key="r.run_id" clickable @click="selected=r"><q-item-section><q-item-label>{{r.run_id.slice(0,12)}}</q-item-label><q-item-label caption>{{r.status}}</q-item-label></q-item-section></q-item></q-list></template>
            <div class="inspector-actions"><q-btn v-if="selected.step_id && !selected.run_id" outline no-caps :label="tr('Plan rerun')" @click="preview(selected.step_id)"/><q-btn v-if="selected.run_id" flat no-caps icon="article" :label="tr('Full log')" @click="act(()=>readLog())"/><q-btn v-if="selected.run_id && selected.status==='SUCCESS'" outline no-caps :label="tr('Use this run')" @click="act(async()=>{await api(`/projects/${project.project_id}/runs/${selected.run_id}/active`,{});await refresh()})"/><q-btn v-if="selected.artifact_id" flat no-caps icon="map" :label="tr('Open map')" @click="openTab('map')"/></div>
          </div></template>
        </aside></template>
      </q-splitter>
      <aside v-if="inspectorAvailable && inspectorCollapsed" class="inspector-rail">
        <button ref="inspectorOpenButton" class="inspector-reopen" :aria-label="t('Show properties panel','展开属性面板')" aria-controls="properties-panel" :aria-expanded="false" @click="toggleInspector(false)">
          <q-icon name="chevron_left" size="20px"/><span class="inspector-rail-label">{{t('Properties','属性')}}</span>
        </button>
      </aside>
      </div></template>
    </q-splitter>
  </q-page></q-page-container>
  <q-footer class="statusbar"><div class="row items-center full-width q-px-md q-gutter-sm"><span class="status-dot" :class="{'status-inactive':!!lifecycleView}"/><span>{{lifecycleView==='exited'?t('Exited','已退出'):lifecycleView==='stopping'?t('Exiting…','正在退出…'):lifecycleView==='offline'?t('Disconnected','连接已断开'):busy?t('Working…','处理中…'):t('Local engine','本机引擎')}}</span><q-separator vertical inset/><span>{{counts.active}} {{t('processing jobs','个处理任务')}}</span><q-btn flat dense no-caps :label="t('Jobs','任务')" @click="openTab('jobs')"/><q-btn flat dense no-caps icon="download" :label="t('Downloads','下载任务')" @click="openTab('downloads')"/><q-btn v-for="j in jobs.filter(j=>j.status==='RUNNING')" :key="j.job_id" flat dense no-caps :label="`Cancel ${j.job_id.slice(0,6)}`" @click="act(async()=>{await api(`/projects/${project.project_id}/jobs/${j.job_id}/cancel`,{});await refresh()})"/><q-space/><span>{{project?profileLabel(project.profile):t('No project open','未打开工程')}}</span></div></q-footer>
</q-layout>
</template>
