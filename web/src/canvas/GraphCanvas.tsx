import {
  Background,
  Controls,
  MiniMap,
  PanOnScrollMode,
  ReactFlow,
  type Connection,
  type Edge,
  type Node,
  type NodeChange,
  type ReactFlowInstance,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useMemo, useRef, useState } from 'react'
import { ClAdversarialNode } from '../nodes/ClAdversarialNode'
import { ClRuleEvalNode } from '../nodes/ClRuleEvalNode'
import { ClRuleTreeNode } from '../nodes/ClRuleTreeNode'
import { DatasetNode } from '../nodes/DatasetNode'
import { EvalNode } from '../nodes/EvalNode'
import { GroupNode } from '../nodes/GroupNode'
import { JudgeNode } from '../nodes/JudgeNode'
import { JudgePromptNode } from '../nodes/JudgePromptNode'
import { LMEngineNode } from '../nodes/LMEngineNode'
import { PeanutSourceNode } from '../nodes/PeanutSourceNode'
import { PreprocessingNode } from '../nodes/PreprocessingNode'
import { nodesInGroup } from '../nodes/geometry'
import { ancestorsOf, descendantsOf } from '../nodes/graphTraversal'
import { isValidSocketConnection } from '../nodes/socketTypes'
import { activeGraphStore, useActiveGraphStore } from '../store/activeTab'
import { usePrefsStore } from '../store/prefsStore'
import { useTheme } from '../theme/ThemeProvider'
import { CanvasContextMenu, type ContextMenuItem } from './CanvasContextMenu'

const NODE_TYPES = {
  peanut_source: PeanutSourceNode,
  dataset: DatasetNode,
  preprocessing: PreprocessingNode,
  lm_engine: LMEngineNode,
  judge_prompt: JudgePromptNode,
  judge: JudgeNode,
  eval: EvalNode,
  cl_rule_eval: ClRuleEvalNode,
  cl_adversarial: ClAdversarialNode,
  cl_rule_tree: ClRuleTreeNode,
  group: GroupNode,
}

interface MenuState {
  x: number
  y: number
  items: ContextMenuItem[]
}

// Snapshot captured when a group starts dragging: which member nodes move with it and where
// they + the group started, so each drag frame translates members by the group's delta.
interface GroupDrag {
  groupId: string
  groupStart: { x: number; y: number }
  members: { id: string; start: { x: number; y: number } }[]
}

export function GraphCanvas() {
  const { theme } = useTheme()
  const panOnScroll = usePrefsStore((s) => s.panOnScroll)
  const nodes = useActiveGraphStore((s) => s.nodes)
  const edges = useActiveGraphStore((s) => s.edges)
  const groups = useActiveGraphStore((s) => s.groups)
  const onNodesChange = useActiveGraphStore((s) => s.onNodesChange)
  const onEdgesChange = useActiveGraphStore((s) => s.onEdgesChange)
  const onConnect = useActiveGraphStore((s) => s.onConnect)
  const selectNode = useActiveGraphStore((s) => s.selectNode)
  const openSecondaryTab = useActiveGraphStore((s) => s.openSecondaryTab)
  const addGroup = useActiveGraphStore((s) => s.addGroup)
  const updateGroup = useActiveGraphStore((s) => s.updateGroup)
  const removeGroup = useActiveGraphStore((s) => s.removeGroup)

  const rfRef = useRef<ReactFlowInstance<Node, Edge> | null>(null)
  const groupDrag = useRef<GroupDrag | null>(null)
  const [menu, setMenu] = useState<MenuState | null>(null)

  const groupIds = useMemo(() => new Set(groups.map((g) => g.id)), [groups])

  // Groups become React Flow nodes of type `group`, rendered BEHIND the real nodes via a
  // negative zIndex, non-selectable (so clicking one never steals the node Inspector's
  // selection) but draggable. Their size is driven by the store's GroupSpec.
  const rfNodes = useMemo<Node[]>(() => {
    const groupNodes: Node[] = groups.map((g) => ({
      id: g.id,
      type: 'group',
      position: g.position,
      width: g.size.width,
      height: g.size.height,
      data: { title: g.title },
      zIndex: -10,
      selectable: false,
      draggable: true,
    }))
    return [...groupNodes, ...nodes]
  }, [groups, nodes])

  // Highlight the full root→leaf path through the selected node(s): every edge whose both
  // endpoints lie in (ancestors ∪ selected ∪ descendants) of some selected node. Uses React
  // Flow's own selection (node.selected), so it covers single- and multi-select.
  const displayEdges = useMemo<Edge[]>(() => {
    const selectedIds = nodes.filter((n) => n.selected).map((n) => n.id)
    if (!selectedIds.length) return edges
    const inPath = new Set<string>()
    for (const sid of selectedIds) {
      inPath.add(sid)
      for (const a of ancestorsOf(edges, sid)) inPath.add(a)
      for (const d of descendantsOf(edges, sid)) inPath.add(d)
    }
    return edges.map((e) =>
      inPath.has(e.source) && inPath.has(e.target)
        ? { ...e, className: 'edge-highlight', animated: true }
        : e,
    )
  }, [edges, nodes])

  const checkValidConnection = (connection: Connection | Edge): boolean => {
    const nodesNow = activeGraphStore().getState().nodes
    const sourceType = nodesNow.find((n) => n.id === connection.source)?.type
    const targetType = nodesNow.find((n) => n.id === connection.target)?.type
    return isValidSocketConnection(
      sourceType, connection.sourceHandle, targetType, connection.targetHandle,
    )
  }

  // Route change events: group ids → updateGroup/removeGroup; everything else → the store's
  // normal node-change handler (the executor nodes).
  const handleNodesChange = (changes: NodeChange<Node>[]) => {
    const nodeChanges: NodeChange<Node>[] = []
    for (const c of changes) {
      const id = 'id' in c ? c.id : undefined
      if (id && groupIds.has(id)) {
        if (c.type === 'position' && c.position) {
          updateGroup(id, { position: c.position })
        } else if (c.type === 'remove') {
          removeGroup(id)
        }
        // Size comes from GroupNode's NodeResizer onResize (authoritative); 'select' and
        // 'dimensions' changes for groups are ignored here.
      } else {
        nodeChanges.push(c)
      }
    }
    if (nodeChanges.length) onNodesChange(nodeChanges as never)
  }

  const handleNodeDragStart = (_e: unknown, node: Node) => {
    if (!groupIds.has(node.id)) return
    const group = groups.find((g) => g.id === node.id)
    if (!group) return
    const memberIds = nodesInGroup(group, nodes)
    groupDrag.current = {
      groupId: node.id,
      groupStart: { ...node.position },
      members: memberIds.map((id) => {
        const n = nodes.find((m) => m.id === id)!
        return { id, start: { x: n.position.x, y: n.position.y } }
      }),
    }
  }

  const handleNodeDrag = (_e: unknown, node: Node) => {
    const drag = groupDrag.current
    if (!drag || node.id !== drag.groupId) return
    const dx = node.position.x - drag.groupStart.x
    const dy = node.position.y - drag.groupStart.y
    // Translate every snapshot member rigidly with the group.
    const changes: NodeChange<Node>[] = drag.members.map((m) => ({
      id: m.id,
      type: 'position',
      position: { x: m.start.x + dx, y: m.start.y + dy },
      dragging: true,
    }))
    if (changes.length) onNodesChange(changes as never)
  }

  const handleNodeDragStop = () => {
    groupDrag.current = null
  }

  const openAddGroupMenu = (e: React.MouseEvent | MouseEvent) => {
    e.preventDefault()
    const flow = rfRef.current?.screenToFlowPosition({ x: e.clientX, y: e.clientY })
    if (!flow) return
    setMenu({
      x: e.clientX,
      y: e.clientY,
      items: [{ label: '＋ Add group here', onClick: () => addGroup(flow) }],
    })
  }

  const openNodeMenu = (e: React.MouseEvent | MouseEvent, node: Node) => {
    if (!groupIds.has(node.id)) return // only groups get a context menu (for now)
    e.preventDefault()
    setMenu({
      x: e.clientX,
      y: e.clientY,
      items: [{ label: '🗑 Remove group', onClick: () => removeGroup(node.id) }],
    })
  }

  return (
    <>
      <ReactFlow
        colorMode={theme}
        nodes={rfNodes}
        edges={displayEdges}
        nodeTypes={NODE_TYPES}
        onInit={(inst) => { rfRef.current = inst }}
        onNodesChange={handleNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        isValidConnection={checkValidConnection}
        onNodeClick={(_, node) => { if (!groupIds.has(node.id)) selectNode(node.id) }}
        onNodeDoubleClick={(_, node) => { if (!groupIds.has(node.id)) openSecondaryTab(node.id) }}
        onNodeDragStart={handleNodeDragStart}
        onNodeDrag={handleNodeDrag}
        onNodeDragStop={handleNodeDragStop}
        onNodeContextMenu={openNodeMenu}
        onPaneContextMenu={openAddGroupMenu}
        onPaneClick={() => { selectNode(null); setMenu(null) }}
        fitView
        // Configurable via the top bar's Settings menu (SettingsMenu.tsx) — pan-on-scroll
        // defaults to on, matching a trackpad's two-finger scroll to "move the board" rather
        // than react-flow's own default of zooming. Pinch-to-zoom and Ctrl/Cmd+scroll always
        // still zoom regardless of this setting.
        panOnScroll={panOnScroll}
        panOnScrollMode={PanOnScrollMode.Free}
        zoomOnScroll={!panOnScroll}
        zoomOnPinch
      >
        <Background />
        <Controls />
        <MiniMap />
      </ReactFlow>
      {menu && (
        <CanvasContextMenu x={menu.x} y={menu.y} items={menu.items} onClose={() => setMenu(null)} />
      )}
    </>
  )
}
