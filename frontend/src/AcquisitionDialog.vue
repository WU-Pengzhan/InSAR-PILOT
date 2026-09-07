<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { api } from './api'
import type { AcquisitionPlan, AcquisitionResult, ProjectTarget, RemoteProduct } from './acquisition'
import { requestId } from './acquisition'
import FilePathField from './FilePathField.vue'
import SearchMap from './SearchMap.vue'
const props = defineProps<{ language: string; products: RemoteProduct[]; project?: ProjectTarget | null; mode: 'download'|'new'|'add' }>()
const open = defineModel<boolean>({default:false})
const emit = defineEmits<{ committed: [result: AcquisitionResult] }>()
const t = (en:string,zh:string) => props.language==='zh'?zh:en
const includeOrbits=ref(true),includeDem=ref(false),margin=ref(20),name=ref(''),path=ref('')
const busy=ref(false),error=ref(''),plan=ref<AcquisitionPlan|null>(null),intent=ref('')
let version=0
const mixed=computed(()=>new Set(props.products.map(p=>p.mission)).size>1)
watch([includeOrbits,includeDem,margin,()=>props.products],()=>{version++;plan.value=null;intent.value=''})
watch([name,path,()=>props.project?.project_id,()=>props.project?.revision,()=>props.mode],()=>{version++;plan.value=null;intent.value=''})
const newProject=computed(()=>props.mode==='new'?{name:name.value,path:path.value,profile:props.products[0]?.mission==='NISAR'?'nisar':'sentinel1_tops',parent_directory:true}:null)
watch(open,value=>{version++;busy.value=false;if(value){error.value='';plan.value=null;intent.value='';includeDem.value=false}})
const bytes=(n:number)=>`${(n/1024**3).toFixed(2)} GiB`
async function review() {
  const ticket=++version;busy.value=true;error.value=''
  try {
    const result=await api<AcquisitionPlan>('/data/acquisition-preview',{
      product_ids:props.products.map(requestId),include_orbits:includeOrbits.value,include_dem:includeDem.value,
      buffer_m:margin.value*1000,project_id:props.mode==='add'?props.project?.project_id:null,new_project:newProject.value,
      query_sources:props.products.map(p=>({product_key:requestId(p),query:p.query_source || {}})),
    })
    if(ticket!==version)return
    plan.value=result;intent.value=crypto.randomUUID()
  } catch(e){if(ticket===version)error.value=(e as Error).message}
  finally{if(ticket===version)busy.value=false;else busy.value=false}
}
async function submit(start:boolean) {
  if(!plan.value||busy.value)return
  busy.value=true;error.value=''
  try {
    const body={plan_id:plan.value.plan_id,idempotency_key:`${intent.value}-${start}`,start_download:start,
      project_id:props.mode==='add'?props.project?.project_id:null,
      expected_revision:plan.value.expected_revision,
      new_project:newProject.value}
    const result=await api<AcquisitionResult>('/data/acquisition-commit',body)
    emit('committed',result);open.value=false
  } catch(e){error.value=(e as Error).message}
  finally{busy.value=false}
}
</script>
<template>
<q-dialog v-model="open" :persistent="busy">
 <q-card class="acquisition-dialog" data-testid="acquisition-dialog">
  <q-card-section class="row items-center"><h2>{{t('Review acquisition','核对获取清单')}}</h2><q-space/><q-btn flat round icon="close" :disable="busy" v-close-popup :aria-label="t('Close','关闭')"/></q-card-section>
  <q-card-section class="acquisition-body">
   <q-banner v-if="error" role="alert" class="bg-red-1 text-red-10">{{error}}</q-banner>
   <p>{{products.length}} {{t('scenes','景影像')}}</p>
   <p v-if="mode==='add'">{{t('Add to project','添加到工程')}}: {{project?.name}}</p>
   <template v-if="mode==='new'"><q-input outlined dense v-model="name" :disable="busy" :label="t('Project name','工程名称')"/><FilePathField :disable="busy" v-model="path" mode="directory" :language="language" :label="t('Save in (parent folder)','保存到（父文件夹）')"/></template>
   <div class="row items-center q-gutter-sm">
    <q-checkbox v-model="includeOrbits" :disable="busy" :label="t('Download precise EOF','下载精密 EOF')"/>
    <q-checkbox v-model="includeDem" :disable="busy || products.some(p=>p.mission!=='SENTINEL-1')" :label="t('Download full-scene DEM','下载整景覆盖 DEM')"/>
   </div>
   <template v-if="includeDem">
    <q-input outlined dense type="number" v-model.number="margin" min="20" max="200" :disable="busy" :label="t('Safety margin (km, minimum 20)','安全余量（km，至少 20）')"/>
    
   </template>
   <q-btn outline color="teal" no-caps :loading="busy" :disable="!products.length || (mode==='new' && (!name.trim() || !path.trim())) || (mixed && mode!=='download')" @click="review" :label="t('Prepare review','生成下载清单')"/>
   <template v-if="plan">
    <p class="destination-label"><q-icon name="folder_open"/> {{plan.destination_kind==='project'?t('Project data','工程数据'):t('Shared library','共享数据仓库')}}</p>
    <p class="path-text destination-path">{{t('Save destination','保存位置')}}: {{plan.destination}}</p>
    <p>{{t('Known download size','已知下载大小')}}: {{bytes(plan.known_bytes)}} + {{plan.unknown_files}} {{t('unknown files','项大小未知')}} · {{t('Free disk','可用空间')}}: {{bytes(plan.free_bytes)}}</p>
    <q-banner v-for="issue in plan.blockers" :key="issue" class="bg-orange-1 text-orange-10 q-mb-sm">{{issue}}</q-banner>
    
    <template v-if="plan.dem">
     <p>{{t('Estimated full-scene DEM extent','预计整景 DEM 范围')}} · {{plan.dem.tile_count}} {{t('tiles','块瓦片')}}</p>
     <SearchMap :editable="false" :aoi="plan.dem.geometry" :products="[]" :selected-ids="[]" :language="language"/>
    </template>
    <q-markup-table flat bordered dense><thead><tr><th>{{t('Scene / role','场景 / 角色')}}</th><th>{{t('State','状态')}}</th></tr></thead><tbody>
     <tr v-for="file in plan.files" :key="file.file_id"><td class="path-text">{{file.scene_id}} · {{file.role==='ORBIT'?'EOF':file.role}}</td><td><span>{{file.status==='available'?t('Available locally','本地已可用'):file.status==='waiting_for_geometry'?t('Waiting for full geometry','等待完整几何'):t('Planned','待获取')}}</span><small v-if="file.local_path" class="block path-text muted">{{t('Reuse reference','复用引用')}}: {{file.local_path}}</small></td></tr>
    </tbody></q-markup-table>
   </template>
  </q-card-section>
  <q-card-actions align="right">
   <q-btn v-if="mode!=='download'" flat no-caps :disable="!plan || busy || (mode==='new' && (!name || !path))" @click="submit(false)" :label="t('Save selection, download later','保存选择，稍后下载')"/>
   <q-btn color="teal-8" unelevated no-caps :loading="busy" :disable="!plan || !!plan.blockers.length || (mode==='new' && (!name || !path))" @click="submit(true)" :label="mode==='download'?t('Start download','开始下载'):t('Save and start download','保存并开始下载')"/>
  </q-card-actions>
 </q-card>
</q-dialog>
</template>
<style scoped>
.acquisition-dialog h2{font-size:22px;line-height:1.4;margin:0}.acquisition-dialog>.q-card__section:first-child{padding:20px;min-height:68px}.acquisition-dialog{width:900px;max-width:94vw;max-height:92vh;display:flex;flex-direction:column}.acquisition-body{overflow:auto;min-height:0}.acquisition-body>*{margin-bottom:12px}.path-text{overflow-wrap:anywhere;white-space:normal!important;max-width:650px}.acquisition-body :deep(.search-leaflet){height:260px;min-height:220px}.q-card-actions{flex-wrap:wrap}
</style>
