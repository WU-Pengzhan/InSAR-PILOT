<script setup lang="ts">
import { computed, onMounted, ref, watch, onBeforeUnmount } from 'vue'
import { api } from './api'
import SearchMap from './SearchMap.vue'
import FilePathField from './FilePathField.vue'
import AcquisitionDialog from './AcquisitionDialog.vue'
import { productKey, requestId, type RemoteProduct, type ProjectTarget, type AcquisitionResult, type DownloadReadiness, type NetworkSettings } from './acquisition'
const props = defineProps<{language:string;projectAvailable:boolean;project?:ProjectTarget|null}>()
const selection=defineModel<RemoteProduct[]>('selection',{default:()=>[]})
const emit=defineEmits<{inspect:[product:RemoteProduct];committed:[result:AcquisitionResult]}>()
const t=(en:string,zh:string)=>props.language==='zh'?zh:en
const sentinelPlatforms=['SENTINEL-1A','SENTINEL-1B','SENTINEL-1C','SENTINEL-1D']
const today=new Date(),earlier=new Date(today.getTime()-90*86400000)
const platforms=ref([...sentinelPlatforms]),mission=ref('SENTINEL-1')
const start=ref(earlier.toISOString().slice(0,10)),end=ref(today.toISOString().slice(0,10))
const mode=ref('bbox'),aoiValue=ref(''),direction=ref(''),orbit=ref<number|null>(null),polarization=ref('')
const frequency=ref('A'),path=ref<number|null>(null),frame=ref<number|null>(null)
interface AOI {geometry:GeoJSON.Geometry;wkt:string;bounds:number[];source?:Record<string,unknown>}
interface SearchGroup {mission:string;error?:string|null;page?:{items:RemoteProduct[];next_page:number|null;total_results?:number|null}|null}
const aoi=ref<AOI|null>(null),groups=ref<SearchGroup[]>([]),readiness=ref<DownloadReadiness|null>(null)
const busy=ref(false),error=ref(''),lastQuery=ref<Record<string,unknown>|null>(null),dirty=ref(false)
const aria2Path=ref(''),gdalPath=ref(''),basket=ref(false)
const readinessOpen=ref(false)
const readinessNeedsAttention=computed(()=>!!readiness.value && (!readiness.value.aria2_available || !readiness.value.credentials_configured || !readiness.value.gdal_available))
const readinessLabel=computed(()=>!readiness.value?t('Checking download environment','正在检查下载环境'):!readiness.value.aria2_available || !readiness.value.credentials_configured?t('Download setup needed','下载环境待配置'):!readiness.value.gdal_available?t('SLC ready · DEM setup needed','影像下载已配置 · DEM 待配置'):t('Download environment configured','下载环境已配置'))
const dialog=ref(false),dialogMode=ref<'download'|'new'|'add'>('download')
const network=ref<NetworkSettings>({mode:'direct',preset:'balanced',http_proxy:'',https_proxy:'',limit_mib:0,timeout_seconds:20})
const products=computed(()=>groups.value.flatMap(g=>g.page?.items||[]))
const selectedIds=computed(()=>selection.value.map(productKey))
const singleMission=computed(()=>new Set(selection.value.map(p=>p.mission)).size===1)
const sizeGiB=computed(()=>selection.value.reduce((n,p)=>n+(p.size_bytes||0),0)/1024**3)
const unknownSizes=computed(()=>selection.value.some(p=>p.size_bytes==null))
const incompatible=computed(()=>!singleMission.value || (!!props.project && props.project.profile!=='unassigned' && props.project.profile!==(selection.value[0]?.mission==='NISAR'?'nisar':'sentinel1_tops')))
const columns=computed(()=>[
 {name:'platform',label:t('Satellite','卫星'),field:'platform',align:'left' as const,sortable:true},
 {name:'date',label:t('Acquired (UTC)','成像时间（UTC）'),field:'acquisition_time',align:'left' as const,sortable:true},
 {name:'orbit',label:t('Relative orbit','相对轨道'),field:'relative_orbit',align:'left' as const,sortable:true},
 {name:'direction',label:t('Direction','轨道方向'),field:'orbit_direction',align:'left' as const},
 {name:'polarization',label:t('Polarization','极化'),field:(r:RemoteProduct)=>r.polarizations.join(', '),align:'left' as const},
 {name:'size',label:'GiB',field:(r:RemoteProduct)=>r.size_bytes==null?'—':(r.size_bytes/1024**3).toFixed(2),align:'right' as const},
 {name:'id',label:t('Product ID','产品 ID'),field:'remote_product_id',align:'left' as const},
])
let generation=0,controller:AbortController|undefined,restoring=false
const storageKey=()=>`pilot-p01-${props.project?.project_id||'global'}`
function persist(){
 if(restoring)return
 try{localStorage.setItem(storageKey(),JSON.stringify({mission:mission.value,platforms:platforms.value,start:start.value,end:end.value,mode:mode.value,aoiValue:aoiValue.value,direction:direction.value,orbit:orbit.value,polarization:polarization.value,frequency:frequency.value,path:path.value,frame:frame.value,selection:selection.value.map(({download_url,...p})=>p)}))}catch{/* Storage quota does not discard live selection. */}
}
function restore(){
 restoring=true;generation++;controller?.abort();busy.value=false;groups.value=[];lastQuery.value=null;aoi.value=null
 try{
  const saved=JSON.parse(localStorage.getItem(storageKey())||'{}')
  mission.value=saved.mission||'SENTINEL-1';platforms.value=saved.platforms||[...sentinelPlatforms]
  start.value=saved.start||earlier.toISOString().slice(0,10);end.value=saved.end||today.toISOString().slice(0,10)
  mode.value=saved.mode||'bbox';aoiValue.value=saved.aoiValue||'';direction.value=saved.direction||'';orbit.value=saved.orbit??null;polarization.value=saved.polarization||''
  frequency.value=saved.frequency||'A';path.value=saved.path??null;frame.value=saved.frame??null
  selection.value=saved.selection||[]
 }catch{selection.value=[]}
 restoring=false
 void resolveSelection()
}
watch(()=>props.project?.project_id,restore,{immediate:true})
watch([mission,platforms,start,end,mode,aoiValue,direction,orbit,polarization,frequency,path,frame],()=>{
 generation++;controller?.abort();busy.value=false;dirty.value=!!lastQuery.value;persist()
},{deep:true,flush:'sync'})
watch(selection,persist,{deep:true})
async function resolveSelection(){
 const context=storageKey()
 if(!selection.value.length)return
 try{
  const resolved=await api<{key:string;product:RemoteProduct|null;available:boolean}[]>('/data/resolve-selection',{product_ids:selection.value.map(requestId)})
  if(context!==storageKey())return
  const byKey=new Map(resolved.map(r=>[r.key,r]))
  selection.value=selection.value.map(p=>{const r=byKey.get(requestId(p));return r?{...p,...(r.product||{}),unavailable:!r.available}:p})
 }catch{/* Keep the basket available while the server is offline. */}
}
async function prepareAOI():Promise<AOI>{
 const ticket=generation,value=aoiValue.value,kind=mode.value
 const region=await api<AOI>('/data/aoi',{mode:kind,value})
 if(ticket!==generation)throw Error(t('AOI changed; apply again.','AOI 已改变，请重新应用。'))
 aoi.value=region;return region
}
async function previewAOI(){const ticket=generation;error.value='';try{await prepareAOI()}catch(e){if(ticket===generation)error.value=(e as Error).message}}
async function drawBounds(value:string){mode.value='bbox';aoiValue.value=value;await previewAOI()}
async function query(){
 const ticket=++generation;controller?.abort();controller=new AbortController();busy.value=true;error.value=''
 try{
  if(!start.value||!end.value||start.value>end.value)throw Error(t('Choose a valid date range.','请选择有效起止日期。'))
  if(mission.value!=='NISAR'&&!platforms.value.length)throw Error(t('Select at least one Sentinel-1 satellite.','请至少选择一颗 Sentinel-1 卫星。'))
  const region=await prepareAOI()
  if(ticket!==generation)return
  const criteria={
   mission:mission.value,start:`${start.value}T00:00:00Z`,end:`${end.value}T23:59:59.999999Z`,aoi_wkt:region.wkt,
   platforms:mission.value!=='NISAR'?[...platforms.value]:[],beam_mode:'IW',product_type:'SLC',
   orbit_direction:direction.value||null,relative_orbit:mission.value==='SENTINEL-1'?orbit.value:null,
   polarizations:mission.value!=='All'&&polarization.value?[polarization.value]:[],
   frequency_bands:mission.value==='NISAR'?[frequency.value]:[],
   provider_options:mission.value==='NISAR'?{'asf-nisar':{...(path.value!=null?{path:path.value}:{}),...(frame.value!=null?{frame:frame.value}:{})}}:{},
  }
  const result=await api<SearchGroup[]>('/data/search',criteria,undefined,controller.signal)
  if(ticket!==generation)return
  groups.value=result.map(g=>({...g,page:g.page?{...g.page,items:g.page.items.map(p=>({...p,query_source:criteria}))}:g.page}))
  lastQuery.value=criteria;dirty.value=false
 }catch(e){if(ticket===generation&&(e as Error).name!=='AbortError')error.value=(e as Error).message}
 finally{if(ticket===generation)busy.value=false}
}
async function loadMore(group:SearchGroup){
 if(!group.page?.next_page||busy.value)return
 const ticket=generation;busy.value=true;error.value=''
 try{
  const result=await api<SearchGroup[]>('/data/search',{...lastQuery.value,mission:group.mission,page:group.page.next_page})
  if(ticket!==generation)return
  const next=result[0]
  if(next.error)throw Error(next.error)
  if(next.page)group.page={...next.page,items:[...new Map([...group.page.items,...next.page.items.map(p=>({...p,query_source:lastQuery.value||{}}))].map(p=>[productKey(p),p])).values()]}
 }catch(e){if(ticket===generation)error.value=(e as Error).message}
 finally{if(ticket===generation)busy.value=false}
}
function select(rows:readonly RemoteProduct[]){
 if(rows.length>1000){error.value=t('Select at most 1000 scenes.','最多选择 1000 景。');return}
 selection.value=[...new Map(rows.map(p=>[productKey(p),p])).values()]
}
function updateTable(rows:readonly RemoteProduct[]){
 const loaded=new Set(products.value.map(productKey))
 select([...selection.value.filter(p=>!loaded.has(productKey(p))),...rows])
}
function inspect(p:RemoteProduct){emit('inspect',p)}
function clear(){
 generation++;controller?.abort();groups.value=[];lastQuery.value=null;error.value='';busy.value=false;dirty.value=false
 mission.value='SENTINEL-1';platforms.value=[...sentinelPlatforms];start.value=earlier.toISOString().slice(0,10);end.value=today.toISOString().slice(0,10)
 mode.value='bbox';aoiValue.value='';aoi.value=null;direction.value='';orbit.value=null;polarization.value='';persist()
}
function acquire(value:'download'|'new'|'add'){if(selection.value.some(p=>p.unavailable)){error.value=t('Remove unavailable scenes from the basket.','请先移除已失效场景。');basket.value=true;return}dialogMode.value=value;dialog.value=true}
async function refreshReadiness(){try{readiness.value=await api<DownloadReadiness>('/data/download-readiness');if(readiness.value.network)network.value={...network.value,...readiness.value.network}}catch(e){error.value=(e as Error).message}}
async function saveDownloadRuntime(){try{readiness.value=await api('/data/download-runtime',{...(aria2Path.value?{aria2_executable:aria2Path.value}:{}),...(gdalPath.value?{gdal_executable:gdalPath.value}:{})});error.value=''}catch(e){error.value=(e as Error).message}}
async function saveNetwork(){try{readiness.value=await api('/data/download-network',network.value);error.value=''}catch(e){error.value=(e as Error).message}}
onMounted(refreshReadiness)
onBeforeUnmount(()=>{generation++;controller?.abort()})
</script>

<template>
  <section class="data-explorer" data-testid="data-explorer">
    <div class="section-heading"><div><div class="eyebrow">{{t('SAR DATA EXPLORER','SAR 数据检索')}}</div><h1>{{t('Find data for your study area','为研究区域查找数据')}}</h1></div><q-badge outline color="teal">ASF DAAC</q-badge></div>
    <q-banner v-if="error" class="bg-red-1 text-red-10 q-mb-md" dense role="alert">{{error}}</q-banner>
    <div class="acquisition-layout">
      <div class="acquisition-controls">
        <h2>{{t('Search criteria','检索条件')}}</h2><q-badge v-if="mission!=='NISAR'" outline color="teal">Sentinel-1 · IW · SLC</q-badge>
        <q-select outlined dense v-model="mission" :options="['SENTINEL-1','NISAR','All']" :label="t('Mission','任务')"/>
        <fieldset v-if="mission!=='NISAR'" class="satellite-selection"><legend>{{t('Sentinel-1 satellites · multi-select','Sentinel-1 卫星 · 可多选')}}</legend><div class="satellite-options"><q-checkbox v-for="satellite in sentinelPlatforms" :key="satellite" v-model="platforms" :val="satellite" :label="satellite.slice(-1)" :aria-label="satellite" color="teal" dense/></div></fieldset>
        <div class="date-pair"><q-input outlined dense type="date" stack-label v-model="start" :label="t('Start date · UTC','开始日期 · UTC')"/><q-input outlined dense type="date" stack-label v-model="end" :label="t('End date · UTC','结束日期 · UTC')"/></div>
        <q-select outlined dense v-model="mode" emit-value map-options :options="[{label:'BBOX',value:'bbox'},{label:'WKT',value:'wkt'},{label:'KML / Shapefile',value:'file'}]" :label="t('AOI format','AOI 格式')"/>
        <FilePathField v-if="mode==='file'" v-model="aoiValue" mode="file" :language="language" :label="t('AOI file','AOI 文件')"/>
        <q-input v-else outlined dense v-model="aoiValue" :type="mode==='wkt'?'textarea':'text'" autogrow :label="mode==='bbox'?t('West, south, east, north','西、南、东、北'):t('WGS84 WKT','WGS84 WKT')"/>
        <q-btn outline dense no-caps icon="center_focus_strong" :label="t('Apply AOI to map','在地图上预览 AOI')" :disable="!aoiValue || busy" @click="previewAOI"/>
        <q-select outlined dense v-model="direction" :options="['','ASCENDING','DESCENDING']" :label="t('Orbit direction · optional','轨道方向 · 可选')"/>
        <q-input v-if="mission==='SENTINEL-1'" outlined dense type="number" v-model.number="orbit" :label="t('Relative orbit · optional','相对轨道 · 可选')" min="1" max="175"/>
        <q-select v-if="mission!=='All'" outlined dense v-model="polarization" :options="mission==='NISAR'?['','HH','HV','VH','VV']:['','VV','VH','VV+VH']" :label="t('Polarization · optional','极化 · 可选')"/>
        <template v-if="mission==='NISAR'"><q-select dense outlined v-model="frequency" :options="['A','B']" :label="t('Frequency','频段')"/><div class="date-pair"><q-input outlined dense type="number" v-model.number="path" label="Path"/><q-input outlined dense type="number" v-model.number="frame" label="Frame"/></div></template>
        <div class="row q-gutter-sm"><q-btn color="teal-8" unelevated no-caps icon="search" :label="t('Search SAR data','检索 SAR 数据')" :loading="busy" @click="query"/><q-btn flat no-caps :label="t('Reset filters','重置筛选')" :disable="busy" @click="clear"/></div>
      </div>
      <div class="acquisition-map"><SearchMap :aoi="aoi?.geometry" :products="products" :selected-ids="selectedIds" :language="language" @bounds="drawBounds" @inspect="inspect"/>
        <div class="download-readiness" data-testid="download-readiness">
          <button class="readiness-summary" type="button" :aria-expanded="readinessOpen" aria-controls="download-readiness-details" @click="readinessOpen=!readinessOpen">
            <q-icon :name="!readiness?'hourglass_empty':readinessNeedsAttention?'info_outline':'check_circle_outline'" :color="readinessNeedsAttention?'orange-8':'teal'"/>
            <span>{{readinessLabel}}</span><q-icon :name="readinessOpen?'expand_less':'expand_more'"/>
          </button>
          <div v-if="readinessOpen" id="download-readiness-details" class="readiness-details">
            <div class="row items-center"><b>{{t('Download settings','下载设置')}}</b><q-space/><q-btn flat dense icon="refresh" :aria-label="t('Refresh download readiness','刷新下载准备状态')" @click="refreshReadiness"/></div>
            <template v-if="readiness"><div class="row q-gutter-sm"><q-chip dense :color="readiness.aria2_available?'teal-1':'orange-1'" text-color="dark">aria2c · {{readiness.aria2_available?t('available','可用'):t('missing','未安装')}}</q-chip><q-chip dense :color="readiness.credentials_configured?'teal-1':'orange-1'" text-color="dark">Earthdata · {{readiness.credentials_configured?t('configured','已配置'):t('not configured','未配置')}}</q-chip></div><p v-if="!readiness.credentials_configured">{{t('Use the existing Earthdata account settings: ~/.netrc or EARTHDATA_USERNAME / EARTHDATA_PASSWORD in the service environment.','沿用原版 Earthdata 账户：在服务环境配置 ~/.netrc 或 EARTHDATA_USERNAME / EARTHDATA_PASSWORD。')}}</p><code class="path-text">{{readiness.library_path}}</code><q-chip dense :color="readiness.gdal_available?'teal-1':'orange-1'" text-color="dark">DEM · GDAL {{readiness.gdal_available?t('available','可用'):t('missing','未配置')}}</q-chip><q-expansion-item :label="t('Download executable','下载程序')" dense><FilePathField v-model="aria2Path" mode="file" :language="language" :label="t('Linux aria2c executable','Linux aria2c 程序')"/><FilePathField v-model="gdalPath" mode="file" :language="language" :label="t('GDAL gdalwarp executable','GDAL gdalwarp 程序')"/><p class="path-text">{{readiness.gdal_executable}}</p><p class="path-text">{{readiness.aria2_executable || t('No executable selected','尚未选择程序')}}</p><q-btn flat dense no-caps :label="t('Use this executable','使用此程序')" :disable="!aria2Path && !gdalPath" @click="saveDownloadRuntime"/></q-expansion-item></template>
          </div>
        </div>
      </div>
    </div>
    <q-banner v-if="dirty" role="status" dense class="q-mt-sm">{{t('Filters changed · search to update','条件已修改 · 检索后更新')}}</q-banner><div class="acquisition-results"><div class="section-heading"><h2>{{t('Search results','检索结果')}} · {{products.length}}</h2><span v-if="lastQuery">{{lastQuery.mission}} · {{String(lastQuery.start).slice(0,10)}} — {{String(lastQuery.end).slice(0,10)}}</span></div>
      <q-banner v-for="group in groups.filter(g=>g.error)" :key="group.mission" dense class="bg-orange-1 text-orange-10 q-mb-sm">{{group.mission}}: {{group.error}}</q-banner>
      <p v-if="!groups.length">{{t('Choose a date range and draw or import an AOI, then search.','设置日期，框选或导入 AOI，然后开始检索。')}}</p>
      <div v-if="products.length" class="selection-toolbar"><q-btn flat dense no-caps :label="t('Select all loaded','全选已加载结果')" @click="select([...selection,...products])"/><q-btn flat dense no-caps :label="t('Select none','取消全选')" @click="selection=selection.filter(p=>!products.some(r=>productKey(r)===productKey(p)))"/><span>{{selection.length}} {{t('selected','项已选择')}} · {{sizeGiB.toFixed(2)}} GiB{{unknownSizes?' + ?':''}}</span></div>
      <q-table v-if="groups.length" flat bordered dense :rows="products"  :row-key="productKey" selection="multiple" :selected="selection.filter(p=>products.some(r=>productKey(r)===productKey(p)))" @update:selected="updateTable" :columns="columns" :loading="busy" :rows-per-page-options="[10,25,50]" @row-click="(_event,row)=>emit('inspect',row)" :no-data-label="t('No acquisitions match this search.','未找到符合条件的影像。')"/>
      <q-btn v-for="group in groups.filter(g=>g.page?.next_page)" :key="group.mission" flat no-caps :label="`${t('Load more','加载更多')} · ${group.mission}`" :loading="busy" @click="loadMore(group)"/>
      <p v-if="selection.length && !singleMission">{{t('For a processing project, select one mission at a time. Download Only can include both missions.','创建或加入处理工程时，请一次选择一种任务。仅下载可以包含两种任务。')}}</p>
      <div class="selection-footer row q-gutter-sm q-mt-md"><q-btn outline no-caps @click="basket=true" :label="`${t('Selected scenes','已选清单')} (${selection.length})`"/><q-btn unelevated no-caps color="teal-8" icon="download" :label="t('Download only','仅下载')" :disable="!selection.length" @click="acquire('download')"/><q-btn outline no-caps :label="t('Create project from selection','从所选数据创建工程')" :disable="!selection.length || !singleMission" @click="acquire('new')"/><q-btn v-if="projectAvailable" flat no-caps :label="t('Add selection to project','添加到当前工程')" :disable="!selection.length || incompatible" @click="acquire('add')"/></div>
    </div>
    <q-expansion-item dense :label="t('Network settings','网络设置')" class="q-mt-md">
      <q-select outlined dense v-model="network.mode" emit-value map-options :options="[{label:t('Direct','直连'),value:'direct'},{label:t('System proxy','系统代理'),value:'environment'},{label:t('Manual proxy','手动代理'),value:'manual'}]" :label="t('Connection mode','连接模式')"/>
      <template v-if="network.mode==='manual'"><q-input outlined dense v-model="network.http_proxy" label="HTTP proxy"/><q-input outlined dense v-model="network.https_proxy" label="HTTPS proxy"/></template>
      <q-select outlined dense v-model="network.preset" emit-value map-options :options="[{label:t('Balanced','均衡'),value:'balanced'},{label:t('Stable','稳定'),value:'stable'}]" :label="t('Transfer preset','传输策略')"/>
      <q-input outlined dense type="number" v-model.number="network.limit_mib" :label="t('Batch SLC limit (MiB/s, 0 = unlimited)','本批影像限速（MiB/s，0 为不限速）')"/>
      
      <q-btn flat no-caps color="teal" @click="saveNetwork" :label="t('Save network settings','保存网络设置')"/>
    </q-expansion-item>
    <q-dialog v-model="basket" position="right">
      <q-card style="width:520px;max-width:94vw"><q-card-section class="row items-center"><h2>{{t('Selected scenes','已选清单')}} · {{selection.length}}</h2><q-space/><q-btn flat icon="close" v-close-popup :aria-label="t('Close','关闭')"/></q-card-section>
      <q-card-section style="max-height:70vh;overflow:auto"><p>{{sizeGiB.toFixed(2)}} GiB{{unknownSizes?' + ?':''}}</p>
       <q-list separator><q-item v-for="p in selection" :key="productKey(p)"><q-item-section><q-item-label class="path-text">{{p.remote_product_id}}</q-item-label><q-item-label v-if="p.unavailable" caption class="text-negative">{{t('Unavailable · remove or search again','已失效 · 请移除或重新检索')}}</q-item-label><q-item-label caption>{{p.platform}} · {{p.acquisition_time}}</q-item-label><q-item-label v-if="!products.some(r=>productKey(r)===productKey(p))" caption>{{t('Outside current results','不在当前结果中')}}</q-item-label></q-item-section><q-item-section side><q-btn flat icon="remove_circle_outline" :aria-label="t('Remove scene','移除场景')" @click="selection=selection.filter(r=>productKey(r)!==productKey(p))"/></q-item-section></q-item></q-list>
      </q-card-section><q-card-actions><q-btn flat no-caps @click="selection=[]" :label="t('Clear entire selection','清空全部已选')"/></q-card-actions></q-card>
    </q-dialog>
    <AcquisitionDialog v-model="dialog" :products="selection" :project="project" :mode="dialogMode" :language="language" @committed="emit('committed',$event)"/>
  </section>
</template>

<style scoped>
.satellite-selection{margin:0;padding:10px 12px 12px;border:1px solid #dae4e2;border-radius:6px;min-width:0}.satellite-selection legend{padding:0 4px;font-size:11px;color:#72858a}.satellite-options{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;font-size:13px}.body--dark .satellite-selection{border-color:#4b5b5d}
.acquisition-controls h2{line-height:1.4}.date-pair{grid-template-columns:1fr!important}.date-pair>*{min-width:0}.date-pair :deep(input){min-width:0}
.data-explorer{container-type:inline-size;max-width:1500px;margin:0 auto;padding-bottom:90px}.selection-footer{position:sticky;bottom:0;z-index:600;background:var(--q-dark-page,#fff);padding:12px;border-top:1px solid #819591;flex-wrap:wrap}.body--light .selection-footer{background:#fff}.path-text{overflow-wrap:anywhere}.acquisition-results :deep(td){max-width:320px;overflow-wrap:anywhere;white-space:normal}.acquisition-layout{display:grid;grid-template-columns:clamp(300px,30%,340px) minmax(0,1fr);gap:18px;align-items:start}.acquisition-controls{min-width:0;display:flex;flex-direction:column;gap:12px;padding:18px;border:1px solid #dae4e2;border-radius:8px}.acquisition-controls h2{margin-bottom:6px}.date-pair{display:grid;grid-template-columns:1fr 1fr;gap:8px}.acquisition-map{min-width:0}.acquisition-map :deep(.search-leaflet){aspect-ratio:auto;height:clamp(320px,calc(100dvh - 280px),720px)}.download-readiness{margin-top:12px;border:1px solid #dae4e2;border-radius:8px}.download-readiness code{font-size:11px}.download-readiness p{margin:8px 0;font-size:12px}.acquisition-results{margin-top:30px}.selection-toolbar{display:flex;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:10px;font-size:12px}.acquisition-help{font-size:11px!important}.body--dark .acquisition-controls,.body--dark .download-readiness{border-color:#31454a}
@container(max-width:620px){.acquisition-layout{grid-template-columns:1fr}.acquisition-controls{display:grid;grid-template-columns:1fr 1fr}.acquisition-controls h2,.acquisition-controls>.row,.acquisition-controls>.date-pair{grid-column:1/-1}}
.readiness-summary{display:flex;align-items:center;gap:8px;width:100%;padding:11px 12px;border:0;border-radius:8px;background:transparent;color:inherit;text-align:left;cursor:pointer;font:inherit;font-size:12px}
.readiness-summary span{flex:1;min-width:0}.readiness-summary:focus-visible{outline:2px solid #279780;outline-offset:2px}.readiness-details{padding:0 12px 14px}
.acquisition-controls :deep(.q-field){min-width:0}.acquisition-controls :deep(.q-field__native){min-width:0}
@container(max-width:400px){.acquisition-controls{display:flex}.date-pair{grid-template-columns:1fr!important}}
</style>
