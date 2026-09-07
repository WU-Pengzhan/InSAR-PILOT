<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import L from 'leaflet'
import { productKey } from './acquisition'
import type { GeoJsonObject } from 'geojson'
import 'leaflet/dist/leaflet.css'

const props = withDefaults(defineProps<{ editable?: boolean; aoi?: GeoJsonObject | null; products: any[]; selectedIds: string[]; language: string }>(), {editable:true})
const emit = defineEmits<{ bounds: [value: string]; inspect: [product: any] }>()
const host = ref<HTMLElement>(), drawing = ref(false), tileError = ref(false)
const t = (en: string, zh: string) => props.language === 'zh' ? zh : en
let tiles: L.TileLayer | undefined
const candidates=ref<any[]>([])
let map: L.Map | undefined, scenes: L.FeatureGroup, aoi: L.FeatureGroup, preview: L.Rectangle | undefined
let start: L.LatLng | undefined, observer: ResizeObserver | undefined
function fit() {
  const bounds = aoi?.getBounds().isValid() ? aoi.getBounds() : scenes?.getBounds()
  if (map && bounds?.isValid()) map.fitBounds(bounds, { padding: [35, 35], maxZoom: 13 })
}
function updateScenes() {
  if (!map) return
  scenes.clearLayers()
  for (const product of props.products) {
    if (!product.footprint?.type) continue
    const chosen = props.selectedIds.includes(productKey(product))
    try {
      const layer = L.geoJSON(product.footprint, { style: { color: chosen ? '#ffd15c' : '#71d8e8', weight: chosen ? 3 : 1.5, fillOpacity: chosen ? .2 : .05 } })
      const label = document.createElement('span'); label.textContent = product.remote_product_id
      layer.bindTooltip(label).on('click', (event: L.LeafletMouseEvent) => {
        if (drawing.value) return
        candidates.value=props.products.filter(p=>{
          try{return L.geoJSON(p.footprint).getBounds().contains(event.latlng)}catch{return false}
        })
        if(candidates.value.length===1){emit('inspect',product);candidates.value=[]}
      })
      scenes.addLayer(layer)
    } catch { /* Invalid provider geometry does not prevent browsing the other scenes. */ }
  }
}
function updateAOI() {
  if (!map) return
  aoi.clearLayers()
  if (props.aoi) aoi.addLayer(L.geoJSON(props.aoi, { style: { color: '#ff9864', weight: 3, fillOpacity: .1 } }))
  fit()
}
function cancelDraw() { drawing.value = false; start = undefined; preview?.remove(); preview = undefined }
onMounted(() => {
  if (!host.value) return
  map = L.map(host.value, { worldCopyJump: false, minZoom: 2, maxZoom: 18 }).setView([25, 100], 3)
  tiles = L.tileLayer('/api/v1/maps/imagery/{z}/{x}/{y}', { noWrap: true, maxZoom: 18, attribution: 'Tiles &copy; Esri', keepBuffer: 3 })
    .on('tileerror', () => { tileError.value = true }).addTo(map)
  scenes = L.featureGroup().addTo(map); aoi = L.featureGroup().addTo(map)
  map.on('click', (event: L.LeafletMouseEvent) => {
    if (!drawing.value) return
    const point = L.latLng(Math.max(-85, Math.min(85, event.latlng.lat)), Math.max(-180, Math.min(180, event.latlng.lng)))
    if (!start) { start = point; return }
    const bounds = L.latLngBounds(start, point)
    if (bounds.getWest() === bounds.getEast() || bounds.getSouth() === bounds.getNorth()) return
    emit('bounds', [bounds.getWest(), bounds.getSouth(), bounds.getEast(), bounds.getNorth()].map(v => v.toFixed(6)).join(', '))
    cancelDraw()
  })
  map.on('mousemove', (event: L.LeafletMouseEvent) => {
    if (!drawing.value || !start || !map) return
    preview?.remove(); preview = L.rectangle(L.latLngBounds(start, event.latlng), { color: '#ff9864', dashArray: '5 5', interactive: false }).addTo(map)
  })
  observer = new ResizeObserver(() => { map?.invalidateSize({ pan: false }); fit() }); observer.observe(host.value)
  updateScenes(); updateAOI()
})
watch(() => props.products, () => { updateScenes(); if (!props.aoi) fit() }, { deep: true })
watch(() => props.selectedIds, updateScenes, { deep: true })
watch(() => props.aoi, updateAOI, { deep: true })
onBeforeUnmount(() => { observer?.disconnect(); map?.remove() })
</script>

<template>
  <div class="search-leaflet" data-testid="search-map">
    <div class="search-map-tools"><q-btn v-if="editable!==false" dense no-caps :color="drawing ? 'orange-9' : 'teal-8'" :label="drawing ? t('Cancel drawing', '取消绘制') : t('Draw AOI', '框选 AOI')" :aria-pressed="drawing" @click="drawing ? cancelDraw() : drawing=true"/><q-btn dense no-caps color="white" text-color="teal-9" :label="t('Fit coverage', '定位覆盖范围')" @click="fit"/></div>
    <div v-if="candidates.length" class="scene-candidates"><b>{{t('Overlapping scenes','此处重叠场景')}}</b><q-btn v-for="p in candidates" :key="productKey(p)" dense flat no-caps :label="p.remote_product_id" @click="emit('inspect',p);candidates=[]"/><q-btn dense flat :label="t('Close','关闭')" @click="candidates=[]"/></div>
    <q-btn v-if="tileError && !drawing" class="tile-retry" dense color="teal-8" :label="t('Retry imagery','重试底图')" @click="tileError=false;tiles?.redraw()"/>
    <div ref="host" tabindex="0" class="leaflet-host" :class="{drawing}" @keydown.esc="cancelDraw"/>
    <div v-if="drawing || tileError" class="imagery-notice">{{ drawing ? t('Click two opposite corners to define the AOI.', '点击两个对角点，框选研究区域。') : t('Imagery unavailable', '底图加载失败') }}</div>
  </div>
</template>

<style scoped>
.scene-candidates{position:absolute;z-index:600;top:60px;right:12px;max-width:80%;max-height:230px;overflow:auto;background:#12262a;color:white;padding:10px;display:flex;flex-direction:column}.tile-retry{position:absolute;z-index:550;bottom:70px;right:12px}
.search-leaflet{height:450px;min-height:330px;position:relative;background:#15252d;border-radius:8px;overflow:hidden;border:1px solid #334b52}
:deep(.leaflet-control-attribution){background:#ffffffdd;color:#263238}:deep(.leaflet-control-attribution a){color:#075e80}.leaflet-host{height:100%;width:100%;background:#15252d}.leaflet-host.drawing{cursor:crosshair}
.search-map-tools{position:absolute;top:12px;right:12px;z-index:500;display:flex;gap:8px}
.imagery-notice{position:absolute;bottom:27px;left:12px;right:12px;z-index:500;background:#12262ae8;color:#fff;padding:8px 12px;border-radius:4px;font-size:12px;pointer-events:none}
</style>
