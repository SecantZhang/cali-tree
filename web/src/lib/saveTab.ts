import { saveWorkflow } from '../api/workflows'
import type { TabRecord } from '../store/tabsStore'
import { useTabsStore } from '../store/tabsStore'

/** Shared by the Workflows-tab save button, the close-tab confirm modal, and the global
 * Cmd+S shortcut — all three write the tab's own graph to a named workflow file, then mark
 * that tab clean under that name. */
export async function saveTabAs(tab: TabRecord, name: string): Promise<void> {
  await saveWorkflow(name, tab.graphStore.getState().toJSON())
  tab.graphStore.getState().setCurrentWorkflowName(name)
  useTabsStore.getState().markClean(tab.tabId, name)
}
