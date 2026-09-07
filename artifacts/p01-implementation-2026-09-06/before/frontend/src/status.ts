export const stateColor = (state: string): string => ({
  SUCCESS: 'positive', PASS: 'positive', FAILED: 'negative', FAIL: 'negative',
  STALE: 'warning', WARNING: 'warning', RUNNING: 'primary', QUEUED: 'info',
  PAUSING: 'warning', PAUSED: 'warning', CANCELLING: 'warning',
}[state] || 'grey-6')

export const latestPerStep = (runs: { step_id: string; run_id: string }[]) =>
  Object.fromEntries(runs.map(run => [run.step_id, run.run_id]))
