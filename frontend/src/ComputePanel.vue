<script setup lang="ts">
import { onMounted, onBeforeUnmount, reactive, ref } from 'vue'
import { api } from './api'
import FilePathField from './FilePathField.vue'
const props = defineProps<{language: string; cpuCount?: number; currentPython?: string; currentProcessor?: string}>()
const t=(en:string,zh:string)=>props.language==='zh'?zh:en
interface Check {name:string;ok:boolean;detail:string}
interface Report {status:string;checked_at:string;python_executable:string;reason:string;checks:Check[]}
const cards=reactive(['isce2','isce3'].map(processor=>({processor,path:'',busy:false,ticket:0,report:null as Report|null,error:''})))
const loading=ref(true), error=ref('')
function detail(value:string){
  if(value.startsWith('missing_module:'))return t('Missing module: ','缺少模块：')+value.slice(15)
  if(value==='unavailable')return t('Not found or check failed','未找到或检查失败')
  return value
}
let active=true
function change(card:typeof cards[number],value:string){card.path=value;card.ticket++;card.busy=false;card.report=null;card.error=''}
function reason(value:string){return ({python_unavailable:t('Python is missing or not executable.','Python 不存在或无法执行。'),probe_failed:t('The environment check could not complete. Check the selected Python and its dependencies.','环境检测未完成，请检查所选 Python 及其依赖。'),probe_timeout:t('The environment check timed out. Try again after checking the environment.','环境检测超时，请检查环境后重试。'),requirements_missing:t('Required components are missing or could not load.','必要组件缺失或无法加载。')})[value] || value}
async function check(card:typeof cards[number],save=false){
  const ticket=++card.ticket,path=card.path.trim();card.busy=true;card.report=null;card.error=''
  try {
    if(save && path) await api('/compute/profiles',{name:card.processor.toUpperCase(),processor:card.processor,python_executable:path})
    if(!active || card.ticket!==ticket)return
    const report=await api<Report>('/compute/check',{processor:card.processor,python_executable:path||null})
    if(active && card.ticket===ticket)card.report=report
  } catch(e){if(active && card.ticket===ticket)card.error=(e as Error).message}
  finally{if(active && card.ticket===ticket)card.busy=false}
}
onMounted(async()=>{
  try{
    const profiles=await api<any[]>('/compute/profiles')
    if(!active)return
    for(const card of cards){card.path=profiles.filter(p=>p.processor===card.processor).at(-1)?.python_executable||''
      if(card.processor===props.currentProcessor && props.currentPython)card.path=props.currentPython}
  }catch(e){error.value=(e as Error).message}
  finally{if(active){loading.value=false;for(const card of cards)void check(card)}}
})
onBeforeUnmount(()=>{active=false})
</script>
<template>
<section class="compute-panel">
  <h1>{{t('Processing environment','处理环境')}}</h1>
  <p>{{t('Check whether the selected environment has the required processing components.','检查所选环境是否具备必要的处理组件。')}} · {{cpuCount || '—'}} CPU</p>
  <q-banner v-if="error" role="alert">{{error}}</q-banner>
  <div class="runtime-cards">
    <article v-for="card in cards" :key="card.processor" class="runtime-card" :data-testid="card.processor+'-runtime'">
      <div class="runtime-heading"><h2>{{card.processor==='isce2'?'Sentinel-1 · ISCE2 TOPS':'NISAR · ISCE3'}}</h2>
        <q-badge :color="card.busy?'grey':card.report?.status==='READY'?'teal':card.report?.status==='UNAVAILABLE'?'negative':'grey'" role="status">{{card.busy?t('Checking…','正在检测…'):card.report?.status==='READY'?t('Environment ready','环境就绪'):card.report?.status==='UNAVAILABLE'?t('Cannot run','当前不可运行'):t('Not verified','尚未确认')}}</q-badge>
      </div>
      <FilePathField :model-value="card.path" @update:model-value="value=>change(card,value)" mode="file" :language="language" :disable="loading || card.busy" :label="t('Processor Python · empty uses the app environment','处理器 Python · 留空使用应用环境')"/>
      <p v-if="card.path===currentPython && card.processor===currentProcessor" class="muted">{{t('Using the current pipeline configuration.','正在检测当前流水线配置。')}}</p>
      <div class="runtime-actions"><q-btn outline no-caps :disable="loading || card.busy" icon="refresh" :label="t('Check again','重新检测')" @click="check(card)"/><q-btn flat no-caps :disable="loading || card.busy || !card.path.trim()" :label="t('Save path and check','保存路径并检测')" @click="check(card,true)"/></div>
      <q-banner v-if="card.error || (card.report && card.report.status!=='READY')" class="runtime-message" role="alert">{{card.error || reason(card.report!.reason)}}</q-banner>
      <template v-if="card.report">
        <p class="runtime-path">{{card.report.python_executable}}</p>
        <ul class="runtime-checks"><li v-for="item in card.report.checks" :key="item.name"><q-icon :name="item.ok?'check_circle':'error'" :color="item.ok?'teal':'negative'"/><strong>{{item.name}}</strong><span>{{item.ok?t('Available','可用'):t('Unavailable','不可用')}}</span><code v-if="item.detail!=='True'">{{detail(item.detail)}}</code></li></ul>
        <p class="muted">{{t('Checked','检测时间')}}: {{new Date(card.report.checked_at).toLocaleString(language==='zh'?'zh-CN':'en-US')}}</p>
      </template>
    </article>
  </div>
  <p class="muted">{{t('This checks CPU runtime dependencies. Input data and scientific results are checked separately. CUDA has not been validated.','此处检查 CPU 运行依赖；输入数据与科学结果另行检查，CUDA 尚未验收。')}}</p>
  <p class="muted">{{t('You manage your environment. Saving a detection path does not change existing pipeline settings.','环境由您自行管理。保存检测路径不会修改已有流水线配置。')}}</p>
</section>
</template>
<style scoped>
.runtime-cards{display:grid;gap:20px;grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr))}.runtime-card{border:1px solid var(--border,#d7e0e6);border-radius:8px;padding:20px;min-width:0}.runtime-heading{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:16px}.runtime-heading h2{font-size:18px;margin:0;flex:1}.runtime-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}.runtime-message{margin-top:16px}.runtime-path{overflow-wrap:anywhere;font-family:monospace;font-size:12px}.runtime-checks{list-style:none;padding:0}.runtime-checks li{display:flex;gap:8px;align-items:baseline;flex-wrap:wrap;padding:8px 0;border-bottom:1px solid var(--border,#d7e0e6)}.runtime-checks code{font-size:12px;overflow-wrap:anywhere;max-width:100%}.muted{font-size:13px}
</style>
