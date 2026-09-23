import type { GraphState, GraphStoreApi } from './graphStore'
import type { RunState, RunStoreApi } from './runStore'
import { useTabsStore } from './tabsStore'

/**
 * `useTabsStore` itself stays a genuine module-level singleton (there is exactly one tab
 * list, always), so it's a reachable anchor from anywhere — including the canvas node
 * renderers (`DatasetNode.tsx` etc.) that `@xyflow/react` mounts with no prop channel from
 * the app shell. That means these hooks don't need a React Context layer: they just look
 * up the active tab's own store instance through the singleton and forward the selector,
 * the same call shape every component already used with the old `useGraphStore`/
 * `useRunStore` singletons.
 */
export function useActiveGraphStore<T>(selector: (s: GraphState) => T): T {
  const graphStore = useTabsStore((s) => s.tabs.find((t) => t.tabId === s.activeTabId)?.graphStore)
  if (!graphStore) {
    throw new Error('useActiveGraphStore: no active tab')
  }
  return graphStore(selector)
}

export function useActiveRunStore<T>(selector: (s: RunState) => T): T {
  const runStore = useTabsStore((s) => s.tabs.find((t) => t.tabId === s.activeTabId)?.runStore)
  if (!runStore) {
    throw new Error('useActiveRunStore: no active tab')
  }
  return runStore(selector)
}

/** Imperative (non-reactive) access to the active tab's stores, for use in event handlers. */
export function activeGraphStore(): GraphStoreApi {
  const tab = useTabsStore.getState().getActiveTab()
  if (!tab) {
    throw new Error('activeGraphStore: no active tab')
  }
  return tab.graphStore
}

export function activeRunStore(): RunStoreApi {
  const tab = useTabsStore.getState().getActiveTab()
  if (!tab) {
    throw new Error('activeRunStore: no active tab')
  }
  return tab.runStore
}
