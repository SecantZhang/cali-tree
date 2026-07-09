import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { fetchCredentialsStatus } from '../../api/settings'
import { useTheme } from '../../theme/ThemeProvider'
import { CredentialsModal } from './CredentialsModal'
import { RunControls } from './RunControls'
import { RunProgress } from './RunProgress'

interface TopBarProps {
  leftPanelCollapsed: boolean
  onToggleLeftPanel: () => void
}

export function TopBar({ leftPanelCollapsed, onToggleLeftPanel }: TopBarProps) {
  const { theme, toggleTheme } = useTheme()
  const [credentialsOpen, setCredentialsOpen] = useState(false)
  const { data: credentialsStatus } = useQuery({
    queryKey: ['credentialsStatus'],
    queryFn: fetchCredentialsStatus,
  })

  return (
    <header className="top-bar-shell">
      <div className="top-bar">
        <button onClick={onToggleLeftPanel} title="Toggle left panel">
          {leftPanelCollapsed ? '»' : '«'}
        </button>
        <strong>VEJudge Interface</strong>
        <RunControls />
        <div className="spacer" />
        <button onClick={() => setCredentialsOpen(true)} title="API credentials">
          <span
            className={`status-dot status-${credentialsStatus?.configured ? 'done' : 'idle'}`}
          />{' '}
          API Key
        </button>
        <button onClick={toggleTheme} title="Toggle theme">
          {theme === 'light' ? 'Dark theme' : 'Light theme'}
        </button>
      </div>
      <RunProgress />
      <CredentialsModal open={credentialsOpen} onClose={() => setCredentialsOpen(false)} />
    </header>
  )
}
