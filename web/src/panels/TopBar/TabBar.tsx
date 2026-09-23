import { useState } from 'react'
import { useTabsStore } from '../../store/tabsStore'
import { CloseTabConfirmModal } from './CloseTabConfirmModal'

export function TabBar() {
  const tabs = useTabsStore((s) => s.tabs)
  const activeTabId = useTabsStore((s) => s.activeTabId)
  const setActiveTab = useTabsStore((s) => s.setActiveTab)
  const closeTab = useTabsStore((s) => s.closeTab)
  const openBlankTab = useTabsStore((s) => s.openBlankTab)
  const [pendingCloseTabId, setPendingCloseTabId] = useState<string | null>(null)

  const requestClose = (tabId: string) => {
    const tab = useTabsStore.getState().getTab(tabId)
    if (tab?.dirty) {
      setPendingCloseTabId(tabId)
    } else {
      closeTab(tabId)
    }
  }

  return (
    <div className="tab-bar">
      {tabs.map((t) => (
        <div
          key={t.tabId}
          className={`tab-item${t.tabId === activeTabId ? ' active' : ''}`}
          onClick={() => setActiveTab(t.tabId)}
        >
          <span className="tab-title">
            {t.title}
            {t.dirty ? ' •' : ''}
          </span>
          <button
            className="tab-close"
            onClick={(e) => {
              e.stopPropagation()
              requestClose(t.tabId)
            }}
            title="Close tab"
          >
            ×
          </button>
        </div>
      ))}
      <button className="tab-add" onClick={() => openBlankTab()} title="New tab" aria-label="New tab">
        +
      </button>
      {pendingCloseTabId && (
        <CloseTabConfirmModal
          tabId={pendingCloseTabId}
          onCancel={() => setPendingCloseTabId(null)}
          onResolved={() => setPendingCloseTabId(null)}
        />
      )}
    </div>
  )
}
