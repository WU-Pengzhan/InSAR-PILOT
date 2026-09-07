<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { QCardActions, QDialog } from 'quasar'
import { api } from './api'

const props = defineProps<{language:string}>()
const emit = defineEmits<{state:[value:string]; jobs:[]}>()
const t = (en:string,zh:string) => props.language==='zh'?zh:en
const status = ref<any>(null), dialog = ref(false), busy = ref(false), error = ref('')
const connection = ref('checking')
let timer:ReturnType<typeof setInterval>|undefined, stopped=false, expectedExit=false, checking=false
const stateLabel = computed(()=>({running:t('Backend running','后台运行中'),stopping:t('Exiting…','正在退出…'),exited:t('Exited','已退出'),offline:t('Disconnected','连接已断开'),checking:t('Checking…','正在检查…')}[connection.value]))
function change(value:string) {if(connection.value!==value){connection.value=value;emit('state',value)}}
async function refresh() {
  if(checking || stopped || connection.value==='exited')return
  checking=true
  try {
    const result=await api('/application/status',undefined,undefined,AbortSignal.timeout(3000))
    status.value=result
    if(result.state==='STOPPING') {expectedExit=true;change('stopping')}
    else if(result.state==='RUNNING' && !expectedExit) {change('running')}
  } catch(e) {
    if((e as {status?:number}).status===401) {change('offline');return}
    change(expectedExit?'exited':'offline')
  } finally {checking=false}
}
async function open() {dialog.value=true;error.value='';await refresh()}
async function exitApplication() {
  busy.value=true;error.value=''
  try {
    await api('/application/shutdown',{},undefined,AbortSignal.timeout(10000))
    expectedExit=true;change('stopping');dialog.value=false
  } catch(e) {error.value=(e as Error).message;await refresh()}
  finally {busy.value=false}
}
onMounted(()=>{void refresh();timer=setInterval(()=>void refresh(),2000)})
onBeforeUnmount(()=>{stopped=true;clearInterval(timer)})
</script>
<template>
  <div class="application-control"><span class="service-status" :class="connection" role="status"><i/>{{stateLabel}}</span><q-btn flat dense no-caps icon="power_settings_new" :label="t('Exit app','退出应用')" :disable="connection!=='running'" @click="open"/></div>
  <q-dialog v-model="dialog"><q-card class="exit-dialog" data-testid="exit-dialog"><q-card-section>
    <div class="exit-title"><q-icon name="power_settings_new" size="27px"/><h2>{{t('Exit InSAR-PILOT','退出 InSAR-PILOT')}}</h2></div>
    <p>{{t('Closing a browser tab keeps the backend and tasks running. Exiting the application stops the local service.','关闭浏览器标签页后，后台服务和任务仍会运行。退出应用才会停止本机后台服务。')}}</p>
    <div v-if="status" class="exit-task-counts"><span>{{status.download_jobs}} {{t('download jobs','个下载任务')}}</span><span>{{status.processing_jobs}} {{t('processing jobs','个处理任务')}}</span><span>{{status.worker_processes}} {{t('worker processes','个工作进程')}}</span></div>
    <q-banner v-if="status && !status.can_exit" dense class="bg-orange-1 text-orange-10">{{t('Tasks or workers are still active. Open Jobs to pause or cancel downloads and cancel processing jobs, then exit.','当前仍有任务或工作进程。请先在任务页暂停或取消下载、取消处理任务，再退出应用。')}}</q-banner>
    <p v-else-if="status?.can_exit">{{t('No active tasks. You can exit now; project records and downloaded files are retained.','当前没有运行中的任务，可以退出。工程记录和已下载文件会保留。')}}</p>
    <q-banner v-if="error" dense class="bg-red-1 text-red-10 q-mt-sm" role="alert">{{error}}</q-banner>
    <p v-if="status && !status.shutdown_supported">{{t('This server does not support app shutdown. Use the insar-pilot-web launcher.','当前服务不支持应用退出，请使用 insar-pilot-web 启动。')}}</p>
  </q-card-section><q-card-actions align="right"><q-btn flat no-caps :label="t('Keep running','保持运行')" @click="dialog=false"/><q-btn v-if="status && !status.can_exit" color="teal" no-caps :label="t('View tasks','查看任务')" @click="dialog=false;emit('jobs')"/><q-btn v-else unelevated no-caps color="teal" :loading="busy" :disable="!status?.can_exit || !status?.shutdown_supported || connection!=='running'" :label="t('Exit application','确认退出')" @click="exitApplication"/></q-card-actions></q-card></q-dialog>
</template>
<style scoped>
.application-control{display:flex;align-items:center;gap:12px;margin-left:12px}.service-status{display:flex;align-items:center;gap:6px;font-size:10px;color:#718888;white-space:nowrap}.service-status i{width:6px;height:6px;border-radius:50%;background:#97a4a5}.service-status.running i{background:#21977e}.service-status.stopping i{background:#c5933f}.exit-dialog{width:500px;max-width:calc(100vw - 40px);border-radius:12px}.exit-dialog .q-card__section{padding:24px}.exit-title{display:flex;align-items:center;gap:12px}.exit-title h2{font-size:20px;line-height:1.4;margin:0}.exit-dialog p{font-size:13px;color:#809292;line-height:1.8}.exit-task-counts{display:flex;flex-wrap:wrap;gap:14px;margin:20px 0;font-size:12px}.exit-dialog .q-card__actions{padding:8px 20px 20px}@media(max-width:1100px){.service-status{display:none}.application-control{margin-left:4px;gap:4px}}
</style>
