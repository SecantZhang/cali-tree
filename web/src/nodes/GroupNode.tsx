import { NodeResizer, type NodeProps } from '@xyflow/react'
import { useActiveGraphStore } from '../store/activeTab'

const MIN_GROUP_WIDTH = 160
const MIN_GROUP_HEIGHT = 120

// A purely-visual, ComfyUI-style group: a translucent rounded rectangle that fills its
// React Flow node, with an editable title bar. Rendered behind the real nodes (a low
// `zIndex` set where the RF node is built, see GraphCanvas). Membership + move-with-members
// are handled by GraphCanvas's drag handlers, not here; this is just the chrome. Resizing
// writes back to the store on every `onResize` tick (NodeResizer gives absolute x/y/w/h) —
// driving the store directly (rather than relying on onNodesChange dimension events) is what
// keeps the size from snapping back to the default as the store-rebuilt node re-renders.
export function GroupNode({ id, data }: NodeProps) {
  const title = (data as { title?: string }).title ?? ''
  const updateGroup = useActiveGraphStore((s) => s.updateGroup)

  return (
    <div className="rf-group">
      {/* Groups are non-selectable, so the resizer is always mounted; its handles are
          revealed on hover via CSS (.react-flow__node-group:hover) rather than on select. */}
      <NodeResizer
        minWidth={MIN_GROUP_WIDTH} minHeight={MIN_GROUP_HEIGHT} isVisible
        lineClassName="rf-group-resize-line" handleClassName="rf-group-resize-handle"
        onResize={(_, p) =>
          updateGroup(id, { position: { x: p.x, y: p.y }, size: { width: p.width, height: p.height } })
        }
      />
      <input
        className="rf-group-title nodrag nopan"
        value={title}
        placeholder="Group"
        onChange={(e) => updateGroup(id, { title: e.target.value })}
      />
    </div>
  )
}
