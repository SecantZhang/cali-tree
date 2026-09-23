import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { saveTabAs } from '../../lib/saveTab'
import { useTabsStore } from '../../store/tabsStore'

interface Props {
  tabId: string
  onCancel: () => void
  onResolved: () => void
}

/** Shown when closing a dirty tab — offers Save (direct, if the tab already names a saved
 * workflow) / Save As (a new name) / Discard / Cancel, per the ComfyUI-style close flow. */
export function CloseTabConfirmModal({ tabId, onCancel, onResolved }: Props) {
  const queryClient = useQueryClient()
  const tab = useTabsStore((s) => s.tabs.find((t) => t.tabId === tabId))
  const [name, setName] = useState(tab?.workflowName ?? '')
  const [busy, setBusy] = useState(false)

  if (!tab) return null

  const doClose = () => {
    useTabsStore.getState().closeTab(tabId)
    onResolved()
  }

  const withSave = async (target: string) => {
    if (!target) return
    setBusy(true)
    try {
      await saveTabAs(tab, target)
      queryClient.invalidateQueries({ queryKey: ['workflows'] })
      doClose()
    } catch (e) {
      window.alert(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div className="modal-panel modal-panel-small" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <strong>Close "{tab.title}" — unsaved changes</strong>
        </div>
        <div className="modal-body">
          <p>This tab has unsaved changes. Save before closing?</p>
          <input
            type="text"
            placeholder="workflow name"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <div className="close-tab-actions">
            {tab.workflowName && (
              <button disabled={busy} onClick={() => withSave(tab.workflowName as string)}>
                Save
              </button>
            )}
            <button disabled={busy || !name} onClick={() => withSave(name)}>
              Save As
            </button>
            <button disabled={busy} onClick={doClose}>
              Discard
            </button>
            <button disabled={busy} onClick={onCancel}>
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
