import { RunControls } from './RunControls'
import { RunProgress } from './RunProgress'
import { SettingsMenu } from './SettingsMenu'
import { activeGraphStore, useActiveGraphStore } from '../../store/activeTab'

interface TopBarProps {
  leftPanelCollapsed: boolean
  onToggleLeftPanel: () => void
}

export function TopBar({ leftPanelCollapsed, onToggleLeftPanel }: TopBarProps) {
  const nodeCount = useActiveGraphStore((s) => s.nodes.length)
  return (
    <header className="top-bar-shell">
      <div className="top-bar">
        <button onClick={onToggleLeftPanel} title="Toggle left panel">
          {leftPanelCollapsed ? '»' : '«'}
        </button>
        <strong>VEJudge Interface</strong>
        <button
          onClick={() => activeGraphStore().getState().autoLayoutNodes()}
          disabled={nodeCount === 0}
          title="Arrange nodes from inputs to outputs"
          aria-label="Auto layout"
        >
          ⇥ Layout
        </button>
        <RunControls />
        <div className="spacer" />
        <SettingsMenu />
      </div>
      <RunProgress />
    </header>
  )
}
