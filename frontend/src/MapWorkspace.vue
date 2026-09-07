<script setup lang="ts">
import {windowUrl} from './window-session'
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import Map from 'ol/Map'
import View from 'ol/View'
import TileLayer from 'ol/layer/Tile'
import VectorLayer from 'ol/layer/Vector'
import XYZ from 'ol/source/XYZ'
import VectorSource from 'ol/source/Vector'
import GeoJSON from 'ol/format/GeoJSON'
import { transformExtent } from 'ol/proj'
import proj4 from 'proj4'
import { register } from 'ol/proj/proj4'

const props = defineProps<{ projectId?: string; artifact?: any; footprints?: any[] }>()
const host = ref<HTMLElement>()
let map: Map | undefined
const vectors = new VectorSource()
let raster: TileLayer<XYZ> | undefined
function update() {
  if (!map) return
  vectors.clear()
  const format = new GeoJSON()
  for (const footprint of props.footprints || []) {
    if (!footprint?.type) continue
    try { vectors.addFeatures(format.readFeatures(footprint, { featureProjection: 'EPSG:3857' })) } catch { /* invalid provider geometry is omitted */ }
  }
  if (raster) { map.removeLayer(raster); raster = undefined }
  const a = props.artifact, spatial = a?.spatial
  if (a && props.projectId && spatial?.grid_kind === 'map' && spatial.bounds && spatial.crs) {
    const epsg = Number(spatial.crs.split(':')[1])
    if (epsg >= 32601 && epsg <= 32760) {
      proj4.defs(spatial.crs, `+proj=utm +zone=${epsg % 100} ${epsg >= 32700 ? '+south' : ''} +datum=WGS84 +units=m +no_defs`)
      register(proj4)
    }
    raster = new TileLayer({ source: new XYZ({ url: windowUrl(`/api/v1/projects/${props.projectId}/artifacts/${a.artifact_id}/tiles/{z}/{x}/{y}.png`), crossOrigin: 'use-credentials' }), opacity: .85 })
    map.addLayer(raster)
    map.getView().fit(transformExtent(spatial.bounds, spatial.crs, 'EPSG:3857'), { padding: [60, 60, 60, 60], maxZoom: 15 })
  } else if (vectors.getFeatures().length) {
    const extent = vectors.getExtent()
    if (extent) map.getView().fit(extent, { padding: [60, 60, 60, 60], maxZoom: 12 })
  }
}
onMounted(() => {
  map = new Map({ target: host.value, layers: [new TileLayer({ source: new XYZ({url:windowUrl('/api/v1/maps/imagery/{z}/{x}/{y}'),attributions:'Tiles © Esri'}) }), new VectorLayer({ source: vectors })], view: new View({ center: [0, 3000000], zoom: 2 }) })
  update()
})
watch(() => [props.artifact, props.footprints], update, { deep: true })
onBeforeUnmount(() => map?.setTarget(undefined))
</script>
<template><div class="map-container"><div ref="host" class="map-host"/><div class="map-caption">{{ artifact?.spatial?.grid_kind === 'radar' ? 'Radar grid · footprint only; open the image workspace for pixel data' : 'Spatial workspace · OpenLayers' }}</div></div></template>
