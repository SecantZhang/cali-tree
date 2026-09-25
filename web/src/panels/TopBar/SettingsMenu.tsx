import { useQuery } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { fetchCredentialsStatus } from '../../api/settings'
import { usePrefsStore } from '../../store/prefsStore'
import { useTheme } from '../../theme/ThemeProvider'
import { CredentialsModal } from './CredentialsModal'

/**
 * Consolidates Theme, API Key, and canvas scroll-behavior into one gear-icon dropdown, so
 * future settings have one obvious home instead of accumulating as loose top-bar buttons.
 * Each control keeps whatever state/persistence it already had (Theme via ThemeProvider's
 * own localStorage write, API Key via CredentialsModal's existing query/mutation, scroll
 * behavior via prefsStore) — this is a pure UI consolidation, not a state-model migration.
 *
 * Deliberately does NOT close this dropdown when opening the Credentials modal: the modal
 * is rendered as this component's own child, so it stays nested inside the click-outside
 * boundary below — closing the modal reveals the dropdown still open underneath, letting
 * "Configure…" be clicked again without reopening the gear icon each time.
 */
export function SettingsMenu() {
  const [open, setOpen] = useState(false)
  const [credentialsOpen, setCredentialsOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const { theme, toggleTheme } = useTheme()
  const panOnScroll = usePrefsStore((s) => s.panOnScroll)
  const setPanOnScroll = usePrefsStore((s) => s.setPanOnScroll)
  const { data: credentialsStatus } = useQuery({
    queryKey: ['credentialsStatus', 'summary'],
    queryFn: async () => {
      const statuses = await Promise.all([fetchCredentialsStatus('openai'), fetchCredentialsStatus('gemini')])
      return { configured: statuses.some((status) => status.configured) }
    },
  })

  useEffect(() => {
    if (!open) return
    function handlePointerDown(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handlePointerDown)
    return () => document.removeEventListener('mousedown', handlePointerDown)
  }, [open])

  return (
    <div className="settings-menu" ref={containerRef}>
      <button
        className="nodrag nopan"
        onClick={() => setOpen((o) => !o)}
        title="Settings"
        aria-label="Settings"
      >
        ⚙
      </button>
      {open && (
        <div className="settings-dropdown">
          <div className="settings-row">
            <span>Theme</span>
            <button onClick={toggleTheme} title="Toggle theme">
              {theme === 'light' ? 'Dark' : 'Light'}
            </button>
          </div>
          <div className="settings-row">
            <span>API Key</span>
            <button onClick={() => setCredentialsOpen(true)} title="API credentials">
              <span
                className={`status-dot status-${credentialsStatus?.configured ? 'done' : 'idle'}`}
              />{' '}
              Configure…
            </button>
          </div>
          <div className="settings-row">
            <span>Canvas scroll</span>
            <select
              value={panOnScroll ? 'pan' : 'zoom'}
              onChange={(e) => setPanOnScroll(e.target.value === 'pan')}
              title="Trackpad two-finger scroll behavior"
            >
              <option value="pan">Pan</option>
              <option value="zoom">Zoom</option>
            </select>
          </div>
        </div>
      )}
      <CredentialsModal open={credentialsOpen} onClose={() => setCredentialsOpen(false)} />
    </div>
  )
}
