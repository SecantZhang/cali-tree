import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { deleteWorkflow, getWorkflow, listWorkflows } from '../../api/workflows'
import { saveTabAs } from '../../lib/saveTab'
import { useTabsStore } from '../../store/tabsStore'

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

  return (
    <div>
      <div className="workflow-save-row">
        <input
          type="text"
          placeholder="workflow name"
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
      {data.length === 0 && <p className="empty-hint">No saved workflows yet.</p>}
      {data.map((n) => (
        <div key={n} className="workflow-item">
          <span>{n}</span>
          <button onClick={() => handleLoad(n)}>Load</button>
          <button onClick={() => deleteMutation.mutate(n)}>Delete</button>
        </div>
      ))}
    </div>
  )
}
