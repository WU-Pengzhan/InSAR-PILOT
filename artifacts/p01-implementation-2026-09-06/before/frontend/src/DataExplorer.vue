<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { QCheckbox } from 'quasar'
import { api } from './api'
import SearchMap from './SearchMap.vue'
import FilePathField from './FilePathField.vue'
const props = defineProps<{ language: string; projectAvailable: boolean }>()
const selection = defineModel<any[]>('selection', { default: () => [] })
const emit = defineEmits<{ inspect: [product: any]; 'create-project': []; 'add-to-project': []; download: [] }>()
const t = (en: string, zh: string) => props.language === 'zh' ? zh : en
const today = new Date(), earlier = new Date(today.getTime() - 90 * 86400000)
const sentinelPlatforms = ['SENTINEL-1A','SENTINEL-1B','SENTINEL-1C','SENTINEL-1D']
const platforms = ref([...sentinelPlatforms])
const mission = ref('SENTINEL-1'), start = ref(earlier.toISOString().slice(0, 10)), end = ref(today.toISOString().slice(0, 10))
const mode = ref('bbox'), aoiValue = ref(''), aoi = ref<any>(null), direction = ref(''), orbit = ref<number | null>(null)
const polarization = ref(''), frequency = ref('A'), path = ref<number | null>(null), frame = ref<number | null>(null)
const aria2Path = ref('')
const groups = ref<any[]>([]), readiness = ref<any>(null), busy = ref(false), error = ref(''), lastQuery = ref<any>(null)
const products = computed(() => groups.value.flatMap(group => group.page?.items || []))
const selectedIds = computed(() => selection.value.map(item => item.remote_product_id))
const singleMission = computed(() => new Set(selection.value.map(item => item.mission)).size === 1)
const sizeGiB = computed(() => selection.value.reduce((sum, item) => sum + (item.size_bytes || 0), 0) / 1024 ** 3)
const unknownSizes = computed(() => selection.value.some(item => item.size_bytes == null))
const columns = computed(() => [
  { name: 'id', label: t('Product', '产品'), field: 'remote_product_id', align: 'left' as const, sortable: true },
  { name: 'mission', label: t('Mission', '任务'), field: 'mission', align: 'left' as const, sortable: true },
  { name: 'date', label: t('Acquired', '成像日期'), field: 'acquisition_time', align: 'left' as const, sortable: true },
  { name: 'orbit', label: t('Orbit', '相对轨道'), field: 'relative_orbit', align: 'left' as const, sortable: true },
  { name: 'direction', label: t('Direction', '轨道方向'), field: 'orbit_direction', align: 'left' as const },
  { name: 'polarization', label: t('Polarization', '极化'), field: (row: any) => row.polarizations.join(', '), align: 'left' as const },
  { name: 'size', label: 'GiB', field: (row: any) => row.size_bytes == null ? '—' : (row.size_bytes / 1024 ** 3).toFixed(2), align: 'right' as const },
])
watch([mode, aoiValue], () => { aoi.value = null })
watch(mission, () => { polarization.value = ''; selection.value = [] })
async function prepareAOI() {
  const value = aoiValue.value, selectedMode = mode.value
  const resolved = await api('/data/aoi', { mode: selectedMode, value })
  if (value !== aoiValue.value || selectedMode !== mode.value) throw Error(t('AOI changed; apply it again.', 'AOI 已改变，请重新应用。'))
  aoi.value = resolved
  return resolved
}
async function previewAOI() { error.value = ''; try { await prepareAOI() } catch(e) { error.value = (e as Error).message } }
async function drawBounds(value: string) { mode.value = 'bbox'; aoiValue.value = value; await previewAOI() }
async function query() {
  busy.value = true; error.value = ''
  try {
    if (!start.value || !end.value || start.value > end.value) throw Error(t('Choose a valid date range.', '请选择有效的起止日期。'))
    if (mission.value !== 'NISAR' && !platforms.value.length) throw Error(t('Select at least one Sentinel-1 satellite.', '请至少选择一颗 Sentinel-1 卫星。'))
    const region = await prepareAOI()
    const criteria = {
      mission: mission.value, start: `${start.value}T00:00:00Z`, end: `${end.value}T23:59:59Z`, aoi_wkt: region.wkt,
      platforms: mission.value !== 'NISAR' ? [...platforms.value] : [],
      orbit_direction: direction.value || null, relative_orbit: mission.value === 'SENTINEL-1' ? orbit.value : null,
      polarizations: mission.value !== 'All' && polarization.value ? [polarization.value] : [],
      frequency_bands: mission.value === 'NISAR' ? [frequency.value] : [],
      provider_options: mission.value === 'NISAR' ? {'asf-nisar': { ...(path.value != null ? {path:path.value} : {}), ...(frame.value != null ? {frame:frame.value} : {}) }} : {},
    }
    groups.value = await api('/data/search', criteria); lastQuery.value = criteria; selection.value = []
  } catch(e) { error.value = (e as Error).message } finally { busy.value = false }
}
async function loadMore(group: any) {
  busy.value = true; error.value = ''
  try {
    const results = await api('/data/search', { ...lastQuery.value, mission: group.mission, page: group.page.next_page })
    const next = results[0]
    if (next.error) throw Error(next.error)
    group.page = {...next.page, items: [...new Map([...group.page.items, ...next.page.items].map((item: any) => [item.remote_product_id, item])).values()]}
  } catch(e) { error.value = (e as Error).message } finally { busy.value = false }
}
function select(rows: readonly any[]) {
  if (rows.length > 1000) { error.value = t('Select at most 1000 products per download.', '每次最多选择 1000 项产品。'); return }
  selection.value = [...rows]
}
function inspect(product: any) { emit('inspect', product); if (!selectedIds.value.includes(product.remote_product_id)) select([...selection.value, product]) }
function clear() { mode.value='bbox'; aoiValue.value=''; groups.value=[]; selection.value=[]; lastQuery.value=null; error.value='' }
async function refreshReadiness() { try { readiness.value = await api('/data/download-readiness') } catch(e) { error.value = (e as Error).message } }
async function saveDownloadRuntime() { try { readiness.value = await api('/data/download-runtime', {aria2_executable:aria2Path.value}); error.value='' } catch(e) {error.value=(e as Error).message} }
onMounted(refreshReadiness)
</script>

<template>
  <section class="data-explorer" data-testid="data-explorer">
    <div class="section-heading"><div><div class="eyebrow">{{t('SAR DATA EXPLORER','SAR 数据检索')}}</div><h1>{{t('Find data for your study area','为研究区域查找数据')}}</h1></div><q-badge outline color="teal">ASF DAAC</q-badge></div>
    <q-banner v-if="error" class="bg-red-1 text-red-10 q-mb-md" dense role="alert">{{error}}</q-banner>
    <div class="acquisition-layout">
      <div class="acquisition-controls">
        <h2>{{t('Search criteria','检索条件')}}</h2>
        <q-select outlined dense v-model="mission" :options="['SENTINEL-1','NISAR','All']" :label="t('Mission','任务')"/>
        <fieldset v-if="mission!=='NISAR'" class="satellite-selection"><legend>{{t('Sentinel-1 satellites · multi-select','Sentinel-1 卫星 · 可多选')}}</legend><div class="satellite-options"><q-checkbox v-for="satellite in sentinelPlatforms" :key="satellite" v-model="platforms" :val="satellite" :label="satellite.slice(-1)" :aria-label="satellite" color="teal" dense/></div></fieldset>
        <div class="date-pair"><q-input outlined dense type="date" stack-label v-model="start" :label="t('Start date','开始日期')"/><q-input outlined dense type="date" stack-label v-model="end" :label="t('End date','结束日期')"/></div>
        <q-select outlined dense v-model="mode" emit-value map-options :options="[{label:'BBOX',value:'bbox'},{label:'WKT',value:'wkt'},{label:'KML / Shapefile',value:'file'}]" :label="t('AOI format','AOI 格式')"/>
        <FilePathField v-if="mode==='file'" v-model="aoiValue" mode="file" :language="language" :label="t('AOI file','AOI 文件')"/>
        <q-input v-else outlined dense v-model="aoiValue" :type="mode==='wkt'?'textarea':'text'" autogrow :label="mode==='bbox'?t('West, south, east, north','西、南、东、北'):t('WGS84 WKT','WGS84 WKT')"/>
        <q-btn outline dense no-caps icon="center_focus_strong" :label="t('Apply AOI to map','在地图上预览 AOI')" :disable="!aoiValue || busy" @click="previewAOI"/>
        <q-select outlined dense v-model="direction" :options="['','ASCENDING','DESCENDING']" :label="t('Orbit direction · optional','轨道方向 · 可选')"/>
        <q-input v-if="mission==='SENTINEL-1'" outlined dense type="number" v-model.number="orbit" :label="t('Relative orbit · optional','相对轨道 · 可选')" min="1" max="175"/>
        <q-select v-if="mission!=='All'" outlined dense v-model="polarization" :options="mission==='NISAR'?['','HH','HV','VH','VV']:['','VV','VH','VV+VH']" :label="t('Polarization · optional','极化 · 可选')"/>
        <template v-if="mission==='NISAR'"><q-select dense outlined v-model="frequency" :options="['A','B']" :label="t('Frequency','频段')"/><div class="date-pair"><q-input outlined dense type="number" v-model.number="path" label="Path"/><q-input outlined dense type="number" v-model.number="frame" label="Frame"/></div></template>
        <div class="row q-gutter-sm"><q-btn color="teal-8" unelevated no-caps icon="search" :label="t('Search SAR data','检索 SAR 数据')" :loading="busy" @click="query"/><q-btn flat no-caps :label="t('Clear','清空')" :disable="busy" @click="clear"/></div>
      </div>
      <div class="acquisition-map"><SearchMap :aoi="aoi?.geometry" :products="products" :selected-ids="selectedIds" :language="language" @bounds="drawBounds" @inspect="inspect"/><p class="acquisition-help">{{t('Orange: AOI · Blue: acquisitions · Yellow: selected. Click a footprint to inspect and select it.','橙色：AOI · 蓝色：影像覆盖 · 黄色：已选择。点击覆盖范围可选择并查看影像。')}}</p>
        <div class="download-readiness" v-if="readiness"><div class="row items-center"><b>{{t('Download preparation','下载准备')}}</b><q-space/><q-btn flat dense icon="refresh" :aria-label="t('Refresh download readiness','刷新下载准备状态')" @click="refreshReadiness"/></div><div class="row q-gutter-sm"><q-chip dense :color="readiness.aria2_available?'teal-1':'orange-1'" text-color="dark">aria2c · {{readiness.aria2_available?t('available','可用'):t('missing','未安装')}}</q-chip><q-chip dense :color="readiness.credentials_configured?'teal-1':'orange-1'" text-color="dark">Earthdata · {{readiness.credentials_configured?t('configured','已配置'):t('not configured','未配置')}}</q-chip></div><p v-if="!readiness.credentials_configured">{{t('Use the existing Earthdata account settings: ~/.netrc or EARTHDATA_USERNAME / EARTHDATA_PASSWORD in the service environment.','沿用原版 Earthdata 账户：在服务环境配置 ~/.netrc 或 EARTHDATA_USERNAME / EARTHDATA_PASSWORD。')}}</p><p>{{t('Downloads use the existing aria2c engine and are saved to the shared Library. Configured credentials are verified when a download starts.','下载沿用原版 aria2c 引擎，保存到共享数据仓库；开始下载时才会验证账户。')}}</p><code class="path-text">{{readiness.library_path}}</code><q-expansion-item :label="t('Download executable','下载程序')" dense><FilePathField v-model="aria2Path" mode="file" :language="language" :label="t('Linux aria2c executable','Linux aria2c 程序')"/><p class="path-text">{{readiness.aria2_executable || t('No executable selected','尚未选择程序')}}</p><q-btn flat dense no-caps :label="t('Use this executable','使用此程序')" :disable="!aria2Path" @click="saveDownloadRuntime"/></q-expansion-item></div>
      </div>
    </div>
    <div class="acquisition-results"><div class="section-heading"><h2>{{t('Search results','检索结果')}} · {{products.length}}</h2><span v-if="lastQuery">{{lastQuery.mission}} · {{lastQuery.start.slice(0,10)}} — {{lastQuery.end.slice(0,10)}}</span></div>
      <q-banner v-for="group in groups.filter(g=>g.error)" :key="group.mission" dense class="bg-orange-1 text-orange-10 q-mb-sm">{{group.mission}}: {{group.error}}</q-banner>
      <p v-if="!groups.length">{{t('Choose a date range and draw or import an AOI, then search.','设置日期，框选或导入 AOI，然后开始检索。')}}</p>
      <div v-if="products.length" class="selection-toolbar"><q-btn flat dense no-caps :label="t('Select all loaded','全选已加载结果')" @click="select(products)"/><q-btn flat dense no-caps :label="t('Select none','取消全选')" @click="selection=[]"/><span>{{selection.length}} {{t('selected','项已选择')}} · {{sizeGiB.toFixed(2)}} GiB{{unknownSizes?' + ?':''}}</span></div>
      <q-table v-if="groups.length" flat bordered dense :rows="products" row-key="remote_product_id" selection="multiple" :selected="selection" @update:selected="select" :columns="columns" :loading="busy" :rows-per-page-options="[10,25,50]" @row-click="(_event,row)=>emit('inspect',row)" :no-data-label="t('No acquisitions match this search.','未找到符合条件的影像。')"/>
      <q-btn v-for="group in groups.filter(g=>g.page?.next_page)" :key="group.mission" flat no-caps :label="`${t('Load more','加载更多')} · ${group.mission}`" :loading="busy" @click="loadMore(group)"/>
      <p v-if="selection.length && !singleMission">{{t('For a processing project, select one mission at a time. Download Only can include both missions.','创建或加入处理工程时，请一次选择一种任务。仅下载可以包含两种任务。')}}</p>
      <div class="row q-gutter-sm q-mt-md"><q-btn unelevated no-caps color="teal-8" icon="download" :label="t('Download only','仅下载')" :disable="!selection.length || !readiness?.ready" @click="emit('download')"/><q-btn outline no-caps :label="t('Create project from selection','从所选数据创建工程')" :disable="!selection.length || !singleMission" @click="emit('create-project')"/><q-btn v-if="projectAvailable" flat no-caps :label="t('Add selection to project','添加到当前工程')" :disable="!selection.length || !singleMission" @click="emit('add-to-project')"/></div>
    </div>
  </section>
</template>

<style scoped>
.satellite-selection{margin:0;padding:10px 12px 12px;border:1px solid #dae4e2;border-radius:6px;min-width:0}.satellite-selection legend{padding:0 4px;font-size:11px;color:#72858a}.satellite-options{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;font-size:13px}.body--dark .satellite-selection{border-color:#4b5b5d}
.acquisition-controls h2{line-height:1.4}.date-pair{grid-template-columns:repeat(2,minmax(0,1fr))!important}.date-pair>*{min-width:0}.date-pair :deep(input){min-width:0}
.data-explorer{max-width:1500px;margin:0 auto}.acquisition-layout{display:grid;grid-template-columns:minmax(245px,300px) minmax(0,1fr);gap:22px}.acquisition-controls{display:flex;flex-direction:column;gap:12px;padding:18px;border:1px solid #dae4e2;border-radius:8px}.acquisition-controls h2{margin-bottom:6px}.date-pair{display:grid;grid-template-columns:1fr 1fr;gap:8px}.acquisition-map{min-width:0}.download-readiness{padding:14px 18px;border:1px solid #dae4e2;border-radius:8px}.download-readiness code{font-size:11px}.download-readiness p{margin:8px 0;font-size:12px}.acquisition-results{margin-top:30px}.selection-toolbar{display:flex;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:10px;font-size:12px}.acquisition-help{font-size:11px!important}.body--dark .acquisition-controls,.body--dark .download-readiness{border-color:#31454a}
@media(max-width:1100px){.acquisition-layout{grid-template-columns:1fr}.acquisition-controls{display:grid;grid-template-columns:1fr 1fr}.acquisition-controls h2,.acquisition-controls>.row,.acquisition-controls>.date-pair{grid-column:1/-1}}
</style>
