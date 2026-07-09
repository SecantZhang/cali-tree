import type { TabRecord } from '../store/tabsStore'
import { useTabsStore } from '../store/tabsStore'
import { useRunSocket } from './useRunSocket'

/** One per open tab, given its own tab record as a plain prop (not looked up via a nested
 * hook call inside another hook's selector — that's invalid and was the source of an
 * infinite-render bug during development). */
function TabRunSocket({ tab }: { tab: TabRecord }) {
  const runId = tab.runStore((rs) => rs.runId)
  useRunSocket(runId, tab.runStore, tab.graphStore)
  return null
}

/**
 * Mounted once at the app root. Every open tab gets its own `useRunSocket` subscription,
 * unconditionally — not just the active one — so a run in a backgrounded tab keeps
 * streaming into that tab's own stores and its progress is never stale when you switch
 * back to it.
 */
export function RunSocketManager() {
  // `s.tabs` itself (not a derived `.map()`/`.find()` result) — zustand keeps this array
  // reference stable across updates that don't touch the tab list (e.g. `setActiveTab`),
  // so this doesn't cause a getSnapshot-instability re-render loop.
  const tabs = useTabsStore((s) => s.tabs)
  return (
    <>
      {tabs.map((tab) => (
        <TabRunSocket key={tab.tabId} tab={tab} />
      ))}
    </>
  )
}
