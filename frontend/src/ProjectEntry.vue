<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { api } from './api'
import type { components } from './api-schema'
import FilePathField from './FilePathField.vue'

const props=defineProps<{mode:'new'|'open';language:string}>()
const emit=defineEmits<{opened:[project:any]}>()
const t=(en:string,zh:string)=>props.language==='zh'?zh:en
type Inspection=components['schemas']['ProjectInspection']
type Preview=components['schemas']['ProjectCreationPreview']
const name=ref(''),parent=ref(''),profile=ref('unassigned'),path=ref('')
const info=ref<Inspection|null>(null),preview=ref<Preview|null>(null)
const error=ref(''),checking=ref(false),saving=ref(false)
const legacy=computed(()=>props.mode==='open' && info.value?.status==='legacy')
let ticket=0,timer:ReturnType<typeof setTimeout>|undefined
const statusText=computed(()=>{
  const status=info.value?.status
  if(status==='ready') return t('Ready to open','可以打开')
  if(status==='legacy') return t('Desktop project · import into a new project','桌面版工程 · 需导入为新工程')
  if(status==='incomplete') return t('Incomplete project · companion database is missing','工程不完整 · 缺少配套数据库')
  if(status==='unsupported') return t('Unsupported project version or format','不支持的工程版本或格式')
  if(status==='conflict') return t('Project identity conflicts with its database or registered location','工程身份与数据库或已登记位置冲突')
  if(status==='modified') return t('External edits require explicit validation and import','工程文件被外部修改，需校验后显式导入修改')
  return t('This file cannot be opened as a project','此文件无法作为工程打开')
})
async function check(id:number) {
  checking.value=true
  try {
    if(props.mode==='open' && path.value.trim()) {
      const result=await api<Inspection>('/projects/inspect',{path:path.value.trim()})
      if(id!==ticket)return
      info.value=result
    }
    if((props.mode==='new'||info.value?.status==='legacy') && name.value.trim() && parent.value.trim()) {
      const result=await api<Preview>('/projects/creation-preview',{name:name.value,path:parent.value,profile:profile.value,parent_directory:true})
      if(id!==ticket)return
      preview.value=result
    }
  } catch(e) {if(id===ticket) error.value=(e as Error).message}
  finally {if(id===ticket)checking.value=false}
}
watch(()=>[props.mode,path.value,name.value,parent.value,profile.value],(current,previous)=>{
  const id=++ticket;clearTimeout(timer);preview.value=null;error.value='';checking.value=true
  // Clear old inspection immediately, so a different path cannot submit stale metadata.
  if(current[0]!==previous[0] || current[1]!==previous[1])info.value=null
  timer=setTimeout(()=>{void check(id)},200)
})
onBeforeUnmount(()=>{ticket++;clearTimeout(timer)})
const canSubmit=computed(()=>!saving.value&&!checking.value&&!error.value && (props.mode==='new'||legacy.value?!!preview.value:info.value?.status==='ready'))
async function submit() {
  if(!canSubmit.value)return
  saving.value=true;error.value=''
  try {
    const result=props.mode==='new'
      ? await api('/projects',{name:name.value,path:parent.value,profile:profile.value,parent_directory:true})
      : legacy.value
        ? await api('/projects/import',{source:path.value,destination:parent.value,name:name.value,parent_directory:true})
        : await api('/projects/open',{path:path.value})
    emit('opened',result)
  } catch(e) {error.value=(e as Error).message}
  finally {saving.value=false}
}
</script>

<template>
  <section class="form-section project-entry">
    <h1>{{mode==='new'?t('New project','新建工程'):t('Open project','打开工程')}}</h1>
    <template v-if="mode==='open'">
      <FilePathField v-model="path" mode="file" extension=".pilot" :disable="saving" :language="language" :label="t('Project file (.pilot)','工程文件（.pilot）')"/>
      <div v-if="info" class="project-entry-summary" :class="{'entry-problem':!['ready','legacy'].includes(info.status)}" role="status">
        <strong>{{statusText}}</strong>
        <dl v-if="info.name"><dt>{{t('Project name','工程名称')}}</dt><dd>{{info.name}}</dd></dl>
        <dl v-if="info.profile"><dt>{{t('Sensor','传感器')}}</dt><dd>{{info.profile}}</dd></dl>
        <dl v-if="info.schema_version"><dt>{{t('Version','版本')}}</dt><dd>{{info.schema_version}}</dd></dl>
        <code class="path-text">{{info.project_file}}</code>
        <p v-if="info.status==='invalid' || info.status==='conflict'">{{info.message}}</p>
      </div>
    </template>
    <template v-if="mode==='new'||legacy">
      <p v-if="legacy">{{t('Import into a new directory and project ID. The original stays intact; missing run evidence remains unknown.','导入为新目录、新工程 ID，保留源工程；缺失的运行证据保持未知。')}}</p>
      <q-input outlined v-model="name" :disable="saving" :label="t('Project name','工程名称')"/>
      <FilePathField v-model="parent" mode="directory" :disable="saving" :language="language" :label="t('Save location','保存到（父文件夹）')"/>
      <q-select v-if="!legacy" outlined v-model="profile" :disable="saving" emit-value map-options :options="[{label:t('Choose after attaching data','绑定数据时确定'),value:'unassigned'},{label:'Sentinel-1 TOPS',value:'sentinel1_tops'},{label:'NISAR',value:'nisar'}]" :label="t('Sensor','传感器')"/>
      <div v-if="preview" class="project-entry-summary" role="status"><strong>{{t('Project file to create','将创建工程文件')}}</strong><dl><dt>{{t('Project folder','工程文件夹')}}</dt><dd class="path-text">{{preview.path}}</dd></dl><code class="path-text">{{preview.project_file}}</code></div>
    </template>
    <q-linear-progress v-if="checking" indeterminate/>
    <q-banner v-if="error" class="bg-red-1 text-red-10" role="alert">{{error}}</q-banner>
    <q-btn unelevated color="teal" no-caps :disable="!canSubmit" :loading="saving" :label="mode==='new'?t('Create project','创建工程'):legacy?t('Import as new project','导入为新工程'):t('Open','打开')" @click="submit"/>
  </section>
</template>
<style scoped>
.project-entry-summary{border:1px solid #c6dcd6;border-radius:8px;padding:16px;display:flex;flex-direction:column;gap:10px;min-width:0}
.project-entry-summary strong{font-size:13px;color:#238573}.project-entry-summary code{font-size:12px}.project-entry-summary dl{display:flex;gap:16px;flex-wrap:wrap}.project-entry-summary dt,.project-entry-summary dd{margin:0}
.entry-problem{border-color:#c6a77d}.entry-problem strong{color:#a67b36}
.body--dark .project-entry-summary{border-color:#37564f}
</style>
