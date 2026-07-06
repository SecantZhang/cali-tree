import { useState } from 'react'
import { GraphCanvas } from './canvas/GraphCanvas'
import { useRunSocket } from './hooks/useRunSocket'
import { Console } from './panels/BottomPanel/Console'
import { LeftPanel } from './panels/LeftPanel/LeftPanel'
import { RightPanel } from './panels/RightPanel/RightPanel'
import { SecondaryTabModal } from './panels/RightPanel/secondary/SecondaryTabModal'
import { TopBar } from './panels/TopBar/TopBar'
import { useRunStore } from './store/runStore'
import './App.css'

function App() {
  const [leftCollapsed, setLeftCollapsed] = useState(false)
  const runId = useRunStore((s) => s.runId)
  useRunSocket(runId)

  return (
    <div className="app-shell">
      <TopBar
        leftPanelCollapsed={leftCollapsed}
        onToggleLeftPanel={() => setLeftCollapsed((c) => !c)}
      />
      <div className="app-body">
        <LeftPanel collapsed={leftCollapsed} />
        <main className="canvas-area">
          <GraphCanvas />
        </main>
        <RightPanel />
      </div>
      <Console />
      <SecondaryTabModal />
    </div>
  )
}

export default App
