import { useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { saveTabAs } from '../lib/saveTab'
import { useTabsStore } from '../store/tabsStore'

/**
 * A single global `keydown` listener (not scoped to canvas focus — the common case is
 * saving right after editing a param in the Inspector, which isn't canvas-focused).
 * Always `preventDefault()`s the browser's native Save-Page-As, then either saves directly
 * (the active tab already names a saved workflow) or falls back to the same Save-As name
 * prompt used elsewhere.
 */
export function useGlobalSaveShortcut() {
  const queryClient = useQueryClient()

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      const isSaveCombo = (e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 's'
      if (!isSaveCombo) return
      e.preventDefault()

      const tab = useTabsStore.getState().getActiveTab()
      if (!tab) return
      const name = tab.workflowName ?? window.prompt('Save as workflow name:', '')
      if (!name) return

      saveTabAs(tab, name)
        .then(() => queryClient.invalidateQueries({ queryKey: ['workflows'] }))
        .catch((err) => window.alert(err instanceof Error ? err.message : String(err)))
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [queryClient])
}
