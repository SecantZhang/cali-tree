export interface WorkflowFolder {
  folders: Record<string, WorkflowFolder>
  workflows: Array<{ label: string; path: string }>
}

export function buildWorkflowTree(paths: string[]): WorkflowFolder {
  const root: WorkflowFolder = { folders: {}, workflows: [] }
  for (const path of [...paths].sort()) {
    const parts = path.split('/')
    const label = parts.pop()
    if (!label) continue
    let folder = root
    for (const part of parts) {
      folder = folder.folders[part] ??= { folders: {}, workflows: [] }
    }
    folder.workflows.push({ label, path })
  }
  return root
}
