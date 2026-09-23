import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import type { ReactNode } from 'react'
import { deleteWorkflow, getWorkflow, listWorkflows } from '../../api/workflows'
import { saveTabAs } from '../../lib/saveTab'
import { useTabsStore } from '../../store/tabsStore'
import { buildWorkflowTree } from './workflowTree'
import type { WorkflowFolder } from './workflowTree'

export function WorkflowsTab() {
  const queryClient = useQueryClient()
  const { data, isLoading, isError } = useQuery({
    queryKey: ['workflows'],
    queryFn: listWorkflows,
  })
  const [name, setName] = useState('')

  const saveMutation = useMutation({
    mutationFn: () => {
      const tab = useTabsStore.getState().getActiveTab()
      if (!tab) throw new Error('no active tab')
      return saveTabAs(tab, name)
    },
    onSuccess: () => {
      setName('')
      queryClient.invalidateQueries({ queryKey: ['workflows'] })
    },
  })
  const deleteMutation = useMutation({
    mutationFn: (n: string) => deleteWorkflow(n),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['workflows'] }),
  })

  // Loading a workflow always opens a new tab — the same saved workflow can be open in
  // more than one tab at once as independent, separately-edited copies.
  const handleLoad = async (n: string) => {
    const wf = await getWorkflow(n)
    useTabsStore.getState().openWorkflowTab(n, wf.graph)
  }

  if (isLoading) return <p className="empty-hint">Loading workflows…</p>
  if (isError || !data) {
    return <p className="empty-hint">Could not reach the backend. Is vejudge-interface running?</p>
  }

  const tree = buildWorkflowTree(data)
  const workflowRow = ({ label, path }: { label: string; path: string }) => (
    <div key={path} className="workflow-item" title={path}>
      <span>{label}</span>
      <button onClick={() => handleLoad(path)}>Load</button>
      <button onClick={() => deleteMutation.mutate(path)}>Delete</button>
    </div>
  )
  const folderRows = (folder: WorkflowFolder, parentPath = ''): ReactNode =>
    Object.entries(folder.folders).map(([folderName, child]) => {
      const folderPath = parentPath ? `${parentPath}/${folderName}` : folderName
      return (
        <details key={folderPath} className="workflow-folder" open>
          <summary title={folderPath}>
            <span className="workflow-folder-icon" aria-hidden="true">▸</span>
            <span>{folderName}</span>
          </summary>
          <div className="workflow-folder-contents">
            {folderRows(child, folderPath)}
            {child.workflows.map(workflowRow)}
          </div>
        </details>
      )
    })

  return (
    <div>
      <div className="workflow-save-row">
        <input
          type="text"
          placeholder="workflow name"
          aria-label="Workflow name or folder/name"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <button
          disabled={!name || saveMutation.isPending}
          onClick={() => saveMutation.mutate()}
        >
          Save current graph
        </button>
      </div>
      <p className="workflow-folder-hint">Use <code>folder/name</code> to save into a folder.</p>
      {data.length === 0 && <p className="empty-hint">No saved workflows yet.</p>}
      <div className="workflow-tree">
        {folderRows(tree)}
        {tree.workflows.map(workflowRow)}
      </div>
    </div>
  )
}
