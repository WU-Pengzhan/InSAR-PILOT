import { describe, expect, it } from 'vitest'
import { mergeEvents, type StateEvent } from './event-cursor'

const event = (sequence: number, event_type = 'run.started'): StateEvent => ({sequence, event_id: String(sequence), event_type, created_at: '', payload: {}})
describe('event cursor replay', () => {
  it('bounds the display while keeping the newest replay cursor',()=>{
    const incoming=Array.from({length:1200},(_,i)=>event(i+1))
    const rows=mergeEvents([],incoming)
    expect(rows).toHaveLength(500)
    expect(rows[0].sequence).toBe(701)
    expect(rows.at(-1)?.sequence).toBe(1200)
    expect(mergeEvents(rows,incoming.slice(0,300))).toEqual(rows)
  })
  it('retains terminal state when a reconnect overlaps prior pages', () => {
    const rows = mergeEvents([event(1), event(2)], [event(2), event(3, 'run.finished')])
    expect(rows.map(e => e.sequence)).toEqual([1, 2, 3])
    expect(mergeEvents(rows, [event(1), event(2)]).at(-1)?.event_type).toBe('run.finished')
  })
})
