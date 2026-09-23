import { existsSync, readFileSync, rmSync } from 'node:fs'

export default async function globalTeardown(): Promise<void> {
  const stateFile = process.env.E2E_STATE_FILE
  if (!stateFile || !existsSync(stateFile)) return

  const state = JSON.parse(readFileSync(stateFile, 'utf-8')) as {
    tmpDir: string
    gatewayPid: number
    backendPid: number
  }

  // SIGKILL, not the default SIGTERM: these are disposable test subprocesses with
  // nothing to flush, and a graceful-shutdown handler running on its own schedule
  // means a SIGTERM'd process can still be alive for a moment after this function
  // returns — SIGKILL removes that ambiguity entirely.
  for (const pid of [state.gatewayPid, state.backendPid]) {
    try {
      process.kill(pid, 'SIGKILL')
    } catch {
      // already exited — fine
    }
  }

  try {
    rmSync(state.tmpDir, { recursive: true, force: true })
  } catch {
    // best-effort cleanup
  }
}
