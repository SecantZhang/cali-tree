import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  type Connection,
  type Edge,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { DatasetNode } from '../nodes/DatasetNode'
import { EvalNode } from '../nodes/EvalNode'
import { JudgeNode } from '../nodes/JudgeNode'
import { isValidSocketConnection } from '../nodes/socketTypes'
import { useGraphStore } from '../store/graphStore'
import { useTheme } from '../theme/ThemeProvider'

const NODE_TYPES = { dataset: DatasetNode, judge: JudgeNode, eval: EvalNode }

export function GraphCanvas() {
  const { theme } = useTheme()
  const nodes = useGraphStore((s) => s.nodes)
  const edges = useGraphStore((s) => s.edges)
  const onNodesChange = useGraphStore((s) => s.onNodesChange)
  const onEdgesChange = useGraphStore((s) => s.onEdgesChange)
  const onConnect = useGraphStore((s) => s.onConnect)
  const selectNode = useGraphStore((s) => s.selectNode)
  const openSecondaryTab = useGraphStore((s) => s.openSecondaryTab)

  const checkValidConnection = (connection: Connection | Edge): boolean => {
    const nodesNow = useGraphStore.getState().nodes
    const sourceType = nodesNow.find((n) => n.id === connection.source)?.type
    const targetType = nodesNow.find((n) => n.id === connection.target)?.type
    return isValidSocketConnection(
      sourceType, connection.sourceHandle, targetType, connection.targetHandle,
    )
  }

  return (
    <ReactFlow
      colorMode={theme}
      nodes={nodes}
      edges={edges}
      nodeTypes={NODE_TYPES}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onConnect={onConnect}
      isValidConnection={checkValidConnection}
      onNodeClick={(_, node) => selectNode(node.id)}
      onNodeDoubleClick={(_, node) => openSecondaryTab(node.id)}
      onPaneClick={() => selectNode(null)}
      fitView
    >
      <Background />
      <Controls />
      <MiniMap />
    </ReactFlow>
  )
}
