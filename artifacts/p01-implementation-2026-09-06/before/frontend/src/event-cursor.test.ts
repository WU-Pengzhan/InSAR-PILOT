import { describe, expect, it } from 'vitest'
import { mergeEvents, type StateEvent } from './event-cursor'

const event = (sequence: number, event_type = 'run.started'): StateEvent => ({sequence, event_id: String(sequence), event_type, created_at: '', payload: {}})
describe('event cursor replay', () => {
  it('retains terminal state when a reconnect overlaps prior pages', () => {
    const rows = mergeEvents([event(1), event(2)], [event(2), event(3, 'run.finished')])
    expect(rows.map(e => e.sequence)).toEqual([1, 2, 3])
    expect(mergeEvents(rows, [event(1), event(2)]).at(-1)?.event_type).toBe('run.finished')
  })
})
