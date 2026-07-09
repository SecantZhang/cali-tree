import { RunControls } from './RunControls'
import { RunProgress } from './RunProgress'
import { SettingsMenu } from './SettingsMenu'

interface TopBarProps {
  leftPanelCollapsed: boolean
  onToggleLeftPanel: () => void
}

export function TopBar({ leftPanelCollapsed, onToggleLeftPanel }: TopBarProps) {
  return (
    <header className="top-bar-shell">
      <div className="top-bar">
        <button onClick={onToggleLeftPanel} title="Toggle left panel">
          {leftPanelCollapsed ? '»' : '«'}
        </button>
        <strong>VEJudge Interface</strong>
        <RunControls />
        <div className="spacer" />
        <SettingsMenu />
      </div>
      <RunProgress />
    </header>
  )
}
