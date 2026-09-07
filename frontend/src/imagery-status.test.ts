import { expect, it } from 'vitest'
import { imageryState } from './imagery-status'

it('distinguishes a partly visible basemap from a complete outage and recovery', () => {
  expect(imageryState(['loaded', 'failed'])).toBe('partial')
  expect(imageryState(['failed', 'failed'])).toBe('unavailable')
  expect(imageryState(['loaded', 'loaded'])).toBe('ready')
})
it('does not declare an outage while current tiles are still loading', () => {
  expect(imageryState(['failed', 'loading'])).toBe('loading')
  expect(imageryState([])).toBe('loading')
})
