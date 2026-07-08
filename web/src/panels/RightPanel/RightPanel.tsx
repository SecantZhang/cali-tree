import { Inspector } from './Inspector'

export function RightPanel({ width }: { width: number }) {
  return (
    <aside className="right-panel" style={{ width }}>
      <Inspector />
    </aside>
  )
}
