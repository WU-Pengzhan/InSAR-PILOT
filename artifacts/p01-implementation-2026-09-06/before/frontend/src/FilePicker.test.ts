// @vitest-environment jsdom
import { DOMWrapper, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { Quasar } from 'quasar'
import * as components from 'quasar'
import { api } from './api'
import FilePathField from './FilePathField.vue'

vi.mock('./api', () => ({ api: vi.fn() }))
const entry = (name: string, kind = 'directory', parent = '/home/user') => ({ name, kind, path: `${parent}/${name}`, resource_id: name })
const home = { ...entry('user', 'directory', '/home'), resource_id: 'home' }
const folder = entry('Inputs'), file = entry('scene.h5', 'file'), safe = entry('scene.SAFE')
const page = (directory = home, entries = [folder, file, safe]) => ({ directory, entries, breadcrumbs: [home, ...(directory === home ? [] : [directory])], parent_id: directory === home ? null : 'home', next_offset: null })
const body = () => new DOMWrapper(document.body)
const button = (text: string) => body().findAll('button').find(item => item.text() === text)!
let wrapper: ReturnType<typeof mount>

beforeEach(() => {
  vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} unobserve() {} })
  vi.mocked(api).mockReset()
  vi.mocked(api).mockImplementation(async (path: string) => {
    if (path === '/filesystem/locations') return { environment: 'wsl', distribution: 'Ubuntu', locations: [home] }
    if (path.includes('/directories/Inputs')) return page(folder, [entry('pair.h5', 'file', folder.path)])
    if (path.includes('/directories/home')) return page()
    throw Error('Missing path')
  })
})
afterEach(() => { wrapper?.unmount(); document.body.innerHTML = ''; vi.unstubAllGlobals() })

async function open(mode: 'directory' | 'new-directory' | 'file' | 'any', multiple = false) {
  wrapper = mount(FilePathField, { props: { modelValue: '', label: 'Inputs', mode, multiple }, attachTo: document.body, global: { plugins: [[Quasar, { components }]] } })
  await wrapper.get('[aria-label="Browse: Inputs"]').trigger('click')
  await flushPromises()
}

it('opens a host folder dialog, navigates without typing and returns the selected Linux path', async () => {
  await open('directory')
  expect(body().text()).toContain('Browsing WSL')
  const row = body().findAll('.q-item').find(item => item.find('.q-item__label').text() === 'Inputs')!
  await row.trigger('click'); await flushPromises()
  await button('Use selection').trigger('click')
  expect(wrapper.emitted('update:modelValue')).toEqual([['/home/user/Inputs']])
})

it('cancel leaves the field untouched and makes no import or creation requests', async () => {
  await open('any', true)
  await body().get('[aria-label="Select scene.h5"]').trigger('click')
  await button('Cancel').trigger('click')
  expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  expect(vi.mocked(api).mock.calls.every(([path]) => path.startsWith('/filesystem/'))).toBe(true)
})

it('selects files and SAFE folders across directories without upload', async () => {
  await open('any', true)
  await body().get('[aria-label="Select scene.h5"]').trigger('click')
  await body().get('[aria-label="Select scene.SAFE"]').trigger('click')
  await body().findAll('.q-item').find(item => item.find('.q-item__label').text() === 'Inputs')!.trigger('click')
  await flushPromises()
  await body().get('[aria-label="Select pair.h5"]').trigger('click')
  await button('Use selection').trigger('click')
  expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['/home/user/scene.h5\n/home/user/scene.SAFE\n/home/user/Inputs/pair.h5'])
})

it('composes a new folder path only on confirmation and rejects path separators', async () => {
  await open('new-directory')
  const name = body().findAll('input').find(input => input.element.closest('.q-field')?.textContent?.includes('New project folder name'))!
  await name.setValue('../outside')
  expect(button('Use selection').attributes('disabled')).toBeDefined()
  await name.setValue('我的工程')
  await button('Use selection').trigger('click')
  expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['/home/user/我的工程'])
  expect(vi.mocked(api).mock.calls.every(([path]) => path.startsWith('/filesystem/'))).toBe(true)
})

it('shows a navigation error and can recover to the previous folder', async () => {
  await open('file')
  vi.mocked(api).mockRejectedValueOnce(Error('Permission denied'))
  await body().findAll('.q-item').find(item => item.find('.q-item__label').text() === 'Inputs')!.trigger('click')
  await flushPromises()
  expect(body().get('[role="alert"]').text()).toContain('Permission denied')
  expect(button('Use selection').attributes('disabled')).toBeDefined()
  await button('Retry').trigger('click'); await flushPromises()
  expect(body().find('[role="alert"]').exists()).toBe(false)
  await body().get('[aria-label="Select scene.h5"]').trigger('click')
  await button('Use selection').trigger('click')
  expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['/home/user/scene.h5'])
})
