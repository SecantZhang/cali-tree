import { useTabsStore } from './tabsStore'

// Checked before showing the --live confirm dialog (both the global Run/Resume buttons in
// RunControls.tsx and the per-node Run/Re-run buttons in SimpleParamNode.tsx) — a
// same-window, zero-round-trip scan of every OTHER open tab's own runStore for a live run
// still in flight.
export function liveRunInAnotherTab(): boolean {
  const { tabs, activeTabId } = useTabsStore.getState()
  return tabs.some((t) => {
    if (t.tabId === activeTabId) return false
    const rs = t.runStore.getState()
    return rs.status === 'running' && rs.isLive
  })
}
