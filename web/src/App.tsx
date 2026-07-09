import { useEffect } from 'react'
import { GraphCanvas } from './canvas/GraphCanvas'
import { ResizeHandle } from './components/ResizeHandle'
import { RunSocketManager } from './hooks/RunSocketManager'
import { useGlobalSaveShortcut } from './hooks/useGlobalSaveShortcut'
import { Console } from './panels/BottomPanel/Console'
import { LeftPanel } from './panels/LeftPanel/LeftPanel'
import { RightPanel } from './panels/RightPanel/RightPanel'
import { SecondaryTabModal } from './panels/RightPanel/secondary/SecondaryTabModal'
import { TabBar } from './panels/TopBar/TabBar'
import { TopBar } from './panels/TopBar/TopBar'
import { usePrefsStore } from './store/prefsStore'
import { useTabsStore } from './store/tabsStore'
import './App.css'

function App() {
  const leftCollapsed = usePrefsStore((s) => s.leftCollapsed)
  const setLeftCollapsed = usePrefsStore((s) => s.setLeftCollapsed)
  const leftWidth = usePrefsStore((s) => s.leftWidth)
  const rightWidth = usePrefsStore((s) => s.rightWidth)
  const bottomHeight = usePrefsStore((s) => s.bottomHeight)
  const hasTabs = useTabsStore((s) => s.tabs.length > 0)
  useGlobalSaveShortcut()

  // No draft persistence across a refresh — a fresh load always starts from a single
  // blank tab; only explicitly-saved workflows survive, as files, same as before tabs
  // existed. Keyed on `hasTabs` (not just mount) so closing the very last open tab also
  // re-opens a blank one instead of leaving the app with no canvas to interact with.
  //
  // Checks fresh store state (`.getState()`), not the closure-captured `hasTabs`: React
  // 18 StrictMode double-invokes effects in development (mount -> cleanup -> mount again,
  // synchronously, before any re-render lets `hasTabs` catch up) — both invocations would
  // otherwise see the same stale `hasTabs === false` and each open their own blank tab,
  // leaving two "Untitled" tabs on every dev-mode page load. A production build (what the
  // E2E suite exercises) compiles this double-invocation out, which is why this was only
  // caught by an actual `npm run dev` visual check, not the automated test suites.
  useEffect(() => {
    if (useTabsStore.getState().tabs.length === 0) {
      useTabsStore.getState().openBlankTab()
    }
  }, [hasTabs])

  if (!hasTabs) return null

  return (
    <div className="app-shell">
      <TopBar
        leftPanelCollapsed={leftCollapsed}
        onToggleLeftPanel={() => setLeftCollapsed(!leftCollapsed)}
      />
      <TabBar />
      <div className="app-body">
        <LeftPanel collapsed={leftCollapsed} width={leftWidth} />
        {!leftCollapsed && (
          <ResizeHandle
            orientation="vertical"
            onResize={(delta) => {
              const s = usePrefsStore.getState()
              s.setLeftWidth(s.leftWidth + delta)
            }}
          />
        )}
        <main className="canvas-area">
          <GraphCanvas />
        </main>
        <ResizeHandle
          orientation="vertical"
          onResize={(delta) => {
            const s = usePrefsStore.getState()
            s.setRightWidth(s.rightWidth - delta)
          }}
        />
        <RightPanel width={rightWidth} />
      </div>
      <ResizeHandle
        orientation="horizontal"
        onResize={(delta) => {
          const s = usePrefsStore.getState()
          s.setBottomHeight(s.bottomHeight - delta)
        }}
      />
      <Console height={bottomHeight} />
      <SecondaryTabModal />
      <RunSocketManager />
    </div>
  )
}

export default App
