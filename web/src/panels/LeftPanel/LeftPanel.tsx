import { useState } from 'react'
import { NodesTab } from './NodesTab'
import { WorkflowsTab } from './WorkflowsTab'
import { DatasetsTab } from './DatasetsTab'

export type LeftTab = 'nodes' | 'workflows' | 'datasets'

const TABS: { id: LeftTab; label: string }[] = [
  { id: 'nodes', label: 'Nodes' },
  { id: 'workflows', label: 'Workflows' },
  { id: 'datasets', label: 'Datasets' },
]

export function LeftPanel({ collapsed, width }: { collapsed: boolean; width: number }) {
  const [tab, setTab] = useState<LeftTab>('nodes')

  return (
    <aside
      className={`left-panel${collapsed ? ' collapsed' : ''}`}
      style={{ width: collapsed ? 0 : width }}
    >
      <div className="tabs">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={t.id === tab ? 'active' : ''}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div className="tab-body">
        {tab === 'nodes' && <NodesTab />}
        {tab === 'workflows' && <WorkflowsTab />}
        {tab === 'datasets' && <DatasetsTab />}
      </div>
    </aside>
  )
}
