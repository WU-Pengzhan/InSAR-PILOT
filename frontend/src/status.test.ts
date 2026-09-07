import { describe, expect, it } from 'vitest'
import { stateColor } from './status'

describe('independent execution, quality and freshness', () => {
  it('makes stale distinct from historical success and failures', () => {
    expect(stateColor('STALE')).not.toBe(stateColor('SUCCESS'))
    expect(stateColor('FAIL')).toBe('negative')
    expect(stateColor('UNKNOWN')).toBe('grey-6')
  })
})
