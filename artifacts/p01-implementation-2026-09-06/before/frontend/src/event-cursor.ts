export interface StateEvent { sequence: number; event_id: string; event_type: string; created_at: string; payload: Record<string, unknown> }

export function mergeEvents(current: StateEvent[], incoming: StateEvent[]): StateEvent[] {
  return [...new Map([...current, ...incoming].map(event => [event.sequence, event])).values()]
    .sort((a, b) => a.sequence - b.sequence)
}
