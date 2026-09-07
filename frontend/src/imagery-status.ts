export type TileState = 'loading' | 'loaded' | 'failed'
export type ImageryState = 'loading' | 'ready' | 'partial' | 'unavailable'

// Only tiles intersecting the current viewport are supplied by SearchMap.
export function imageryState(states: TileState[]): ImageryState {
  if (!states.length || states.includes('loading')) return 'loading'
  const failures = states.filter(s => s === 'failed').length
  return failures === states.length ? 'unavailable' : failures ? 'partial' : 'ready'
}
