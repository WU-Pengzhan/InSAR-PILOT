// @vitest-environment jsdom
import { mount, flushPromises } from '@vue/test-utils'
import { beforeEach, expect, it, vi } from 'vitest'
import { Quasar } from 'quasar'
import * as components from 'quasar'
import App from './App.vue'

vi.mock('./api', () => ({
  api: vi.fn(async (path: string) => path === '/compute' ? {cpu_count: 4} : []),
  connectEvents: vi.fn(() => () => {}),
}))
beforeEach(() => { localStorage.clear(); vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} unobserve() {} }) })
it('shows empty project state and opens the real creation form', async () => {
  const wrapper = mount(App, { global: { plugins: [[Quasar, {components}]] } })
  await flushPromises()
  expect(wrapper.text()).toContain('Recent projects')
  expect(wrapper.text()).toContain('Your project history starts here')
  const button = wrapper.findAll('button').find(b => b.text() === 'New project')!
  await button.trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain('Project folder')
  expect(wrapper.text()).not.toContain('Submit this plan')
  wrapper.unmount()
})
