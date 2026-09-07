<script setup lang="ts">
import { ref } from 'vue'
import FilePicker from './FilePicker.vue'

const props = withDefaults(defineProps<{
  modelValue: string; label: string; mode: 'directory' | 'new-directory' | 'file' | 'any'
  multiple?: boolean; language?: string
}>(), { multiple: false, language: 'en' })
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
const visible = ref(false)
function choose(paths: string[]) {
  const existing = props.multiple ? props.modelValue.split('\n').filter(Boolean) : []
  emit('update:modelValue', [...new Set([...existing, ...paths])].join('\n'))
}
</script>

<template>
  <div class="file-path-field">
    <q-input outlined :model-value="modelValue" :label="label" :type="multiple ? 'textarea' : 'text'" :autogrow="multiple" @update:model-value="emit('update:modelValue', String($event ?? ''))">
      <template #append><q-btn flat dense no-caps icon="folder_open" :aria-label="`${language === 'zh' ? '浏览' : 'Browse'}: ${label}`" :label="language === 'zh' ? '浏览' : 'Browse'" @click="visible = true"/></template>
    </q-input>
    <FilePicker v-model="visible" :initial-path="modelValue.split('\n').filter(Boolean).at(-1) || ''" :mode="mode" :multiple="multiple" :language="language" @select="choose"/>
  </div>
</template>
