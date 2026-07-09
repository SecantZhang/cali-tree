import { create } from 'zustand'
import { createGraphStore, type GraphSpecJSON, type GraphStoreApi } from './graphStore'
import { createRunStore, type RunStoreApi } from './runStore'

export interface TabRecord {
  tabId: string
  title: string
  workflowName: string | null
  dirty: boolean
  graphStore: GraphStoreApi
  runStore: RunStoreApi
}

interface TabsState {
  tabs: TabRecord[]
  activeTabId: string | null
  openBlankTab: () => string
  openWorkflowTab: (name: string, graph: GraphSpecJSON) => string
  closeTab: (tabId: string) => void
  setActiveTab: (tabId: string) => void
  markDirty: (tabId: string) => void
  markClean: (tabId: string, workflowName: string | null) => void
  renameTab: (tabId: string, title: string, workflowName: string | null) => void
  getTab: (tabId: string) => TabRecord | undefined
  getActiveTab: () => TabRecord | undefined
}

let tabCounter = 0
function nextTabId(): string {
  tabCounter += 1
  return `tab-${tabCounter}`
}

function makeTab(title: string): TabRecord {
  const tabId = nextTabId()
  const tab: TabRecord = {
    tabId,
    title,
    workflowName: null,
    dirty: false,
    graphStore: createGraphStore(() => useTabsStore.getState().markDirty(tabId)),
    runStore: createRunStore(),
  }
  return tab
}

export const useTabsStore = create<TabsState>((set, get) => ({
  tabs: [],
  activeTabId: null,

  openBlankTab: () => {
    const tab = makeTab('Untitled')
    set((s) => ({ tabs: [...s.tabs, tab], activeTabId: tab.tabId }))
    return tab.tabId
  },

  // Always opens a NEW tab — the same saved workflow can be open in two tabs at once as
  // independent, separately-edited copies (confirmed during Stage B planning).
  openWorkflowTab: (name, graph) => {
    const tab = makeTab(name)
    tab.graphStore.getState().loadGraph(graph)
    tab.graphStore.getState().setCurrentWorkflowName(name)
    tab.workflowName = name
    set((s) => ({ tabs: [...s.tabs, tab], activeTabId: tab.tabId }))
    return tab.tabId
  },

  closeTab: (tabId) => {
    set((s) => {
      const idx = s.tabs.findIndex((t) => t.tabId === tabId)
      if (idx === -1) return s
      const tabs = s.tabs.filter((t) => t.tabId !== tabId)
      let activeTabId = s.activeTabId
      if (activeTabId === tabId) {
        const fallback = tabs[idx] ?? tabs[idx - 1]
        activeTabId = fallback ? fallback.tabId : null
      }
      return { tabs, activeTabId }
    })
  },

  setActiveTab: (tabId) => set({ activeTabId: tabId }),

  markDirty: (tabId) => {
    // A no-op bail-out once already dirty — this runs on every content-mutating graphStore
    // action (including every frame of a node-drag gesture), so skipping the allocation
    // entirely when there's nothing to change keeps it genuinely O(1) amortized, not just
    // O(1) per call.
    const current = get().tabs.find((t) => t.tabId === tabId)
    if (!current || current.dirty) return
    set((s) => ({
      tabs: s.tabs.map((t) => (t.tabId === tabId ? { ...t, dirty: true } : t)),
    }))
  },

  markClean: (tabId, workflowName) => {
    set((s) => ({
      tabs: s.tabs.map((t) =>
        t.tabId === tabId ? { ...t, dirty: false, workflowName, title: workflowName ?? t.title } : t,
      ),
    }))
  },

  renameTab: (tabId, title, workflowName) => {
    set((s) => ({
      tabs: s.tabs.map((t) => (t.tabId === tabId ? { ...t, title, workflowName } : t)),
    }))
  },

  getTab: (tabId) => get().tabs.find((t) => t.tabId === tabId),
  getActiveTab: () => get().tabs.find((t) => t.tabId === get().activeTabId),
}))
