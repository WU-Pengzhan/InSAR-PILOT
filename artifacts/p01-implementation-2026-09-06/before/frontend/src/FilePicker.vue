<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { QCardActions, QCheckbox, QDialog } from 'quasar'
import { api } from './api'
import type { components } from './api-schema'

type Entry = components['schemas']['FileEntry']
type Page = components['schemas']['DirectoryPage']
type Locations = components['schemas']['FileLocations']
type Resolved = components['schemas']['ResolvedPath']
const props = withDefaults(defineProps<{
  modelValue: boolean; initialPath?: string; mode: 'directory' | 'new-directory' | 'file' | 'any'
  multiple?: boolean; language?: string
}>(), { initialPath: '', multiple: false, language: 'en' })
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; select: [paths: string[]] }>()
const t = (en: string, zh: string) => props.language === 'zh' ? zh : en
const locations = ref<Locations | null>(null), page = ref<Page | null>(null)
const selected = ref<Entry[]>([]), address = ref(''), search = ref(''), hidden = ref(false)
const newName = ref(''), error = ref(''), loading = ref(false)
let request = 0
const directoriesOnly = computed(() => ['directory', 'new-directory'].includes(props.mode))
const validName = computed(() => !newName.value || (!['.', '..'].includes(newName.value) && !/[\\/\x00-\x1f]/.test(newName.value)))
const chosen = computed(() => {
  if (!page.value) return []
  if (directoriesOnly.value) {
    const parent = page.value.directory.path
    return [props.mode === 'new-directory' && newName.value ? `${parent.replace(/\/$/, '')}/${newName.value}` : parent]
  }
  return selected.value.map(entry => entry.path)
})
const canSelect = computed(() => !loading.value && !error.value && chosen.value.length > 0 && validName.value)

const breadcrumbsHost = ref<HTMLElement>()
const entriesHost = ref<{ $el: HTMLElement }>()
const title = computed(() => directoriesOnly.value ? t('Choose a folder', '选择文件夹') : props.mode === 'file' ? t('Choose a file', '选择文件') : t('Choose files or folders', '选择文件或文件夹'))
function place(entry: Entry, index: number) {
  if (index === 0) return { label: t('Home folder','主目录'), icon:'home', kind:'home' }
  if (index === 1 && entry.path !== '/') return { label:t('Data Library','数据仓库'),icon:'inventory_2',kind:'library' }
  if (entry.path === '/') return {label:t('File system','文件系统'),icon:'dns',kind:'root'}
  if (entry.path === '/mnt') return {label:t('Mounted disks','挂载磁盘'),icon:'storage',kind:'mounts'}
  const drive = locations.value?.environment === 'wsl' && entry.path.match(/^\/mnt\/([a-z])$/i)
  if (drive) return {label:`Windows (${drive[1].toUpperCase()}:)`,icon:'storage',kind:'drive'}
  return {label:entry.name,icon:'folder_open',kind:'folder'}
}
watch(() => page.value?.directory.path, async () => {
  await nextTick()
  if (breadcrumbsHost.value) breadcrumbsHost.value.scrollLeft = breadcrumbsHost.value.scrollWidth
  if (entriesHost.value) entriesHost.value.$el.scrollTop = 0
})

async function load(id: string, offset = 0, reset = false) {
  const ticket = ++request
  loading.value = true; error.value = ''
  if (reset) search.value = ''
  try {
    const query = new URLSearchParams({ offset: String(offset), search: search.value, hidden: String(hidden.value), directories_only: String(directoriesOnly.value) })
    const result = await api<Page>(`/filesystem/directories/${encodeURIComponent(id)}?${query}`)
    if (ticket !== request) return
    if (offset && page.value?.directory.resource_id === id) result.entries = [...page.value.entries, ...result.entries]
    page.value = result; address.value = result.directory.path
  } catch (e) { if (ticket === request) error.value = (e as Error).message }
  finally { if (ticket === request) loading.value = false }
}
async function go(value = address.value) {
  const ticket = ++request
  loading.value = true; error.value = ''
  try {
    const result = await api<Resolved>('/filesystem/resolve', { path: value })
    if (ticket !== request) return
    if (result.entry.kind === 'file' && !directoriesOnly.value) toggle(result.entry)
    await load(result.directory_id, 0, true)
  } catch (e) { if (ticket === request) error.value = (e as Error).message }
  finally { if (ticket === request) loading.value = false }
}
function toggle(entry: Entry) {
  if (selected.value.some(item => item.path === entry.path)) selected.value = selected.value.filter(item => item.path !== entry.path)
  else if (!props.multiple) selected.value = [entry]
  else if (selected.value.length < 1000) selected.value = [...selected.value, entry]
}
function close() { request++; emit('update:modelValue', false) }
function confirm() { if (canSelect.value) { emit('select', chosen.value); close() } }
watch(() => props.modelValue, async visible => {
  const ticket = ++request
  if (!visible) return
  page.value = null; selected.value = []; search.value = ''; newName.value = ''; error.value = ''; loading.value = true
  try {
    const roots = await api<Locations>('/filesystem/locations')
    if (ticket !== request) return
    locations.value = roots
    if (props.initialPath) {
      try {
        const resolved = await api<Resolved>('/filesystem/resolve', { path: props.initialPath })
        if (ticket !== request) return
        if (resolved.entry.kind === 'file' && !directoriesOnly.value) selected.value = [resolved.entry]
        await load(resolved.directory_id)
        return
      } catch {
        // A not-yet-created project should reopen at its chosen parent.
        const match = props.mode === 'new-directory' && props.initialPath.match(/^(.*[/\\])([^/\\]+)$/)
        if (match && ticket === request) {
          try {
            const parent = await api<Resolved>('/filesystem/resolve', { path: match[1] })
            if (ticket !== request) return
            if (parent.entry.kind === 'directory') {
              newName.value = match[2]
              await load(parent.directory_id)
              return
            }
          } catch { /* Still allow choosing a different location below. */ }
        }
      }
      if (ticket !== request) return
    }
    if (roots.locations.length) await load(roots.locations[0].resource_id)
    else throw Error(t('No readable locations available.', '没有可读取的位置。'))
  } catch (e) { if (ticket === request) error.value = (e as Error).message }
  finally { if (ticket === request) loading.value = false }
})
</script>

<template>
  <q-dialog class="picker-dialog" :model-value="modelValue" @update:model-value="value => !value && close()">
    <q-card class="file-picker" data-testid="file-picker" role="region" :aria-label="title">
      <header class="picker-header">
        <div class="picker-title-icon"><q-icon name="folder_open" size="24px"/></div>
        <div class="picker-title"><h2>{{title}}</h2><span>{{locations?.environment === 'wsl' ? t('Browsing WSL','正在浏览 WSL') : t('Local Linux files','Linux 本地文件')}}<template v-if="locations?.distribution"> · {{locations.distribution}}</template></span></div>
        <q-btn flat round dense icon="close" :aria-label="t('Close file browser', '关闭文件选择窗口')" @click="close"/>
      </header>
      <div class="picker-location-bar">
        <div class="picker-address-row">
          <q-btn flat round dense icon="arrow_upward" :aria-label="t('Parent folder', '上级目录')" :disable="loading || !page?.parent_id" @click="page?.parent_id && load(page.parent_id, 0, true)"/>
          <q-input class="picker-address" dense outlined v-model="address" :label="t('Location (optional: paste a path)', '当前位置（也可粘贴路径）')" @keyup.enter="go()"><template #prepend><q-icon name="folder_open" size="18px"/></template></q-input>
          <q-btn flat dense no-caps icon="arrow_forward" :label="t('Go', '前往')" :disable="loading || !address" @click="go()"/>
        </div>
        <nav ref="breadcrumbsHost" class="picker-breadcrumbs" :aria-label="t('Folder path', '目录路径')"><template v-for="(entry,index) in page?.breadcrumbs" :key="entry.resource_id"><q-icon v-if="index" name="chevron_right" size="15px"/><q-btn flat dense no-caps :class="{'current-crumb':entry.path===page?.directory.path}" :aria-current="entry.path===page?.directory.path?'location':undefined" :label="entry.name==='/'?t('File system','文件系统'):entry.name" :title="entry.path" :disable="loading" @click="load(entry.resource_id, 0, true)"/></template></nav>
      </div>
      <div class="picker-body">
        <aside class="picker-places" :aria-label="t('Places','常用位置')">
          <div class="picker-section-label">{{t('Places','常用位置')}}</div>
          <button v-for="(entry,index) in locations?.locations" :key="entry.resource_id" type="button" class="picker-place" :class="{'active-place':page?.directory.path===entry.path}" :data-location-kind="place(entry,index).kind" :title="entry.path" :disabled="loading" @click="load(entry.resource_id,0,true)"><q-icon :name="place(entry,index).icon" size="19px"/><span>{{place(entry,index).label}}</span></button>
          <p class="picker-host-hint">{{locations?.environment==='wsl'?t('Windows files are available through mounted disks.','Windows 文件可从挂载磁盘进入。'):t('Folders on the computer running InSAR-PILOT.','浏览运行 InSAR-PILOT 的计算机。')}}</p>
        </aside>
        <div class="picker-directory">
          <div class="picker-filter"><q-input dense outlined v-model="search" :debounce="250" :label="t('Filter this folder', '筛选当前目录')" @update:model-value="page && load(page.directory.resource_id)"><template #prepend><q-icon name="search" size="18px"/></template></q-input><q-checkbox v-model="hidden" dense :label="t('Hidden files', '隐藏文件')" @update:model-value="page && load(page.directory.resource_id)"/></div>
          <q-banner v-if="error" dense class="picker-error bg-red-1 text-red-10" role="alert">{{error}}<template #action><q-btn flat no-caps :label="t('Retry','重试')" @click="page ? load(page.directory.resource_id) : go()"/></template></q-banner>
          <div class="picker-loading"><q-linear-progress v-if="loading" indeterminate/></div>
          <div class="picker-list-heading"><span>{{t('Name','名称')}}</span><span>{{t('Type','类型')}}</span></div>
          <q-list ref="entriesHost" class="picker-entries" :aria-busy="loading" :aria-label="t('Files and folders', '文件和文件夹')">
            <q-item v-for="entry in page?.entries" :key="entry.resource_id" clickable :disable="loading" :active="selected.some(item => item.path === entry.path)" @click="entry.kind === 'directory' ? load(entry.resource_id, 0, true) : toggle(entry)">
              <q-item-section v-if="!directoriesOnly && (mode === 'any' || entry.kind === 'file')" side><q-checkbox dense :model-value="selected.some(item => item.path === entry.path)" :aria-label="`${t('Select','选择')} ${entry.name}`" @click.stop @update:model-value="toggle(entry)"/></q-item-section>
              <q-item-section avatar><q-icon :name="entry.kind === 'directory' ? 'folder' : 'description'" :color="entry.kind === 'directory' ? 'teal' : undefined" size="21px"/></q-item-section>
              <q-item-section><q-item-label class="picker-name" :title="entry.name">{{entry.name}}</q-item-label></q-item-section>
              <q-item-section side class="picker-entry-type">{{entry.kind==='directory'?t('Folder','文件夹'):t('File','文件')}}</q-item-section>
              <q-item-section side><q-icon v-if="entry.kind==='directory'" name="chevron_right" size="18px"/><span v-else class="picker-file-spacer"/></q-item-section>
            </q-item>
            <div v-if="page && !page.entries.length && !loading" class="picker-empty"><q-icon name="folder_open" size="36px"/><span>{{t('No matching items in this folder.','当前目录没有匹配的项目。')}}</span></div>
          </q-list>
          <div class="picker-list-status"><span>{{loading?t('Loading…','正在加载…'):`${page?.entries.length || 0} ${t('items loaded','项已加载')}`}}</span><q-btn v-if="page?.next_offset != null" flat dense no-caps :disable="loading" :label="t('Load more','加载更多')" @click="load(page.directory.resource_id,page.next_offset)"/></div>
        </div>
      </div>
      <footer class="picker-footer" :class="{'picker-new-folder':mode==='new-directory'}">
        <q-input v-if="mode==='new-directory'" class="picker-new-name" outlined dense stack-label v-model="newName" :label="t('New project folder name (optional)','新工程文件夹名称（可选）')" :error="!validName" :error-message="t('Use a folder name without slashes, . or ..','请填写不含斜杠的文件夹名，不能为 . 或 ..')" :hint="t('Created when you submit the project. Leave empty to use this empty folder.','提交新建工程时才会创建。留空则使用当前空文件夹。')"/>
        <div v-if="directoriesOnly" class="picker-selection-path" :title="chosen[0]"><q-icon name="folder_open" size="18px"/><span class="picker-selection-label">{{t('Selected path:','所选路径：')}} <span class="picker-path-value">{{chosen[0] || '—'}}</span></span></div>
        <div v-else class="picker-selection-files"><div class="picker-selection-summary"><q-btn v-if="mode==='any' && page" flat dense no-caps :disable="loading" :label="t('Select this folder','选择当前文件夹')" @click="toggle(page.directory)"/><span>{{selected.length}} / {{multiple ? 1000 : 1}} {{t('selected','项已选择')}}</span></div><div class="picker-selected-chips"><q-chip v-for="entry in selected" :key="entry.path" removable :title="entry.path" @remove="toggle(entry)"><span class="ellipsis">{{entry.name}}</span></q-chip></div></div>
        <div class="picker-footer-actions"><span>{{t('Local references · no file upload','本地路径引用 · 无需上传文件')}}</span><q-card-actions><q-btn flat no-caps :label="t('Cancel','取消')" @click="close"/><q-btn unelevated no-caps color="teal" :label="t('Use selection','使用所选项')" :disable="!canSelect" @click="confirm"/></q-card-actions></div>
      </footer>
    </q-card>
  </q-dialog>
</template>

<style scoped>
:global(.picker-dialog .q-dialog__inner--minimized){padding:8px}
.file-picker{width:920px!important;max-width:calc(100vw - 40px)!important;height:700px;max-height:calc(100dvh - 40px)!important;display:flex;flex-direction:column;overflow:hidden!important;border-radius:14px!important;color:#263e44;background:#fff}
.picker-header{display:flex;align-items:center;gap:14px;padding:18px 22px;flex:none;border-bottom:1px solid #e5eceb}.picker-title-icon{width:42px;height:42px;display:grid;place-items:center;background:#e8f4f0;color:#167f6d;border-radius:12px}.picker-title{flex:1;min-width:0}.picker-title h2{font-size:18px;font-weight:600;line-height:1.4;margin:0}.picker-title>span{font-size:11px;color:#7a8d91}
.picker-location-bar{padding:12px 18px 8px;flex:none}.picker-address-row{display:flex;align-items:center;gap:8px;min-width:0}.picker-address{flex:1;min-width:0}.picker-address :deep(input){font-family:ui-monospace,monospace;font-size:12px}.picker-address :deep(.q-field__control){border-radius:8px;background:#f9fbfa}.picker-breadcrumbs{display:flex;align-items:center;gap:2px;overflow-x:auto;white-space:nowrap;height:34px;margin:5px 0 0 40px;scrollbar-width:thin}.picker-breadcrumbs>*{flex-shrink:0}.picker-breadcrumbs .q-btn{max-width:150px;font-size:12px;color:#71878c;padding:0 8px}.picker-breadcrumbs :deep(.q-btn__content){display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.picker-breadcrumbs .current-crumb{color:#157c69;background:#eaf5f0;font-weight:600;border-radius:6px}
.picker-body{display:grid;grid-template-columns:180px minmax(0,1fr);flex:1;min-height:0;border-top:1px solid #e5eceb;border-bottom:1px solid #e5eceb}.picker-places{background:#f5f8f7;border-right:1px solid #e5eceb;padding:18px 10px;overflow:auto;min-width:0}.picker-section-label{font-size:10px;letter-spacing:1px;text-transform:uppercase;font-weight:600;color:#7b9394;padding:0 12px 12px}.picker-place{width:100%;display:flex;align-items:center;gap:10px;padding:11px 12px;margin:2px 0;border:0;border-radius:7px;background:transparent;color:#587176;text-align:left;cursor:pointer;font:inherit;font-size:12px}.picker-place span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.picker-place:hover,.active-place{background:#e2eee9;color:#146d5b}.picker-place:focus-visible{outline:2px solid #19816d;outline-offset:-2px}.picker-place:disabled{opacity:.55;cursor:wait}.picker-host-hint{font-size:11px;color:#7d9295;line-height:1.7;margin:22px 12px 0}
.picker-directory{display:flex;flex-direction:column;min-width:0;min-height:0}.picker-filter{display:flex;gap:16px;align-items:center;padding:12px 18px 8px;flex:none}.picker-filter>.q-field{flex:1;min-width:0}.picker-filter .q-checkbox{font-size:12px;flex-shrink:0}.picker-loading{height:4px;flex:none}.picker-list-heading{display:flex;justify-content:space-between;padding:8px 52px 8px 22px;background:#fafcfc;color:#8b9a9c;font-size:11px;flex:none}.picker-entries{flex:1;min-height:0;overflow:auto;overscroll-behavior:contain;scrollbar-gutter:stable}.picker-entries .q-item{min-height:42px;padding:8px 18px;font-size:12px}.picker-entries .q-item__section--avatar{min-width:32px;padding-right:10px}.picker-entries .q-item__section--main{min-width:0}.picker-name{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.picker-entry-type{font-size:11px;color:#8b9a9c}.picker-file-spacer{width:18px}.picker-empty{height:100%;min-height:90px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:12px;color:#91a3a5;font-size:12px}.picker-list-status{height:34px;padding:0 18px;display:flex;align-items:center;justify-content:space-between;flex:none;border-top:1px solid #eef2f1;color:#7e9598;font-size:11px}.picker-error{max-height:90px;overflow:auto;flex:none;overflow-wrap:anywhere}
.picker-footer{padding:12px 20px 6px;flex:none}.picker-selection-path{display:flex;align-items:center;gap:10px;background:#f2f7f5;border:1px solid #e5eeea;border-radius:7px;padding:8px 12px;min-width:0;height:38px;font-size:11px;color:#6f8688}.picker-selection-label{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.picker-path-value{font-family:ui-monospace,monospace;color:#365650}.picker-footer-actions{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-top:6px}.picker-footer-actions>span{font-size:10px;color:#879b9c}.picker-footer-actions .q-card__actions{flex:none;padding:4px 0;gap:6px}.picker-footer-actions .q-btn{font-size:12px}.picker-new-name{height:72px}.picker-new-name :deep(.q-field__bottom){padding-top:5px;font-size:10px}.picker-selection-files{height:62px;display:flex;flex-direction:column;gap:2px}.picker-selection-summary{display:flex;align-items:center;gap:10px;height:26px;font-size:11px;color:#718b8d}.picker-selection-summary .q-btn{font-size:11px}.picker-selected-chips{display:flex;overflow-x:auto;min-height:32px;white-space:nowrap;scrollbar-width:thin}.picker-selected-chips .q-chip{flex-shrink:0;max-width:240px;height:25px;font-size:11px}
.body--dark .file-picker{background:#1a2a30;color:#d4e5e3}.body--dark .picker-header,.body--dark .picker-body,.body--dark .picker-places,.body--dark .picker-list-status{border-color:#31464c}.body--dark .picker-title-icon,.body--dark .active-place,.body--dark .picker-place:hover{background:#25443f;color:#82cdb9}.body--dark .picker-places{background:#17252b}.body--dark .picker-place{color:#a8c0c0}.body--dark .picker-address :deep(.q-field__control),.body--dark .picker-list-heading{background:#1d3036}.body--dark .picker-breadcrumbs .current-crumb{color:#85d5be;background:#26443e}.body--dark .picker-selection-path{background:#203932;border-color:#314d43}.body--dark .picker-path-value{color:#b6d8ca}
@media(max-width:640px){.file-picker{max-width:calc(100vw - 16px)!important;max-height:calc(100dvh - 16px)!important}.picker-body{grid-template-columns:126px minmax(0,1fr)}.picker-places{padding:12px 5px}.picker-place{padding:10px 6px;gap:6px}.picker-host-hint{display:none}.picker-filter{gap:8px;padding:10px}.picker-filter .q-checkbox{font-size:10px}.picker-entry-type{display:none}.picker-footer-actions>span{display:none}.picker-footer-actions{justify-content:flex-end}.picker-header{padding:12px 16px}.picker-footer{padding:10px 12px 6px}}
@media(max-height:620px){.file-picker{max-height:calc(100dvh - 16px)!important}.picker-header{padding:10px 16px}.picker-title-icon{width:34px;height:34px}.picker-title h2{font-size:16px}.picker-location-bar{padding:6px 12px}.picker-breadcrumbs{height:28px;margin-top:2px}.picker-filter{padding:8px 14px 4px}.picker-list-heading{padding-top:5px;padding-bottom:5px}.picker-list-status{height:30px}.picker-footer{padding:8px 14px 4px}.picker-new-name{height:64px}.picker-selection-path{height:32px}.picker-footer-actions{margin-top:2px}}
</style>
