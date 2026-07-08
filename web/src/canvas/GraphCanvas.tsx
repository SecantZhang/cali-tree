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
import { LMEngineNode } from '../nodes/LMEngineNode'
import { PeanutSourceNode } from '../nodes/PeanutSourceNode'
import { PreprocessingNode } from '../nodes/PreprocessingNode'
import { TextJudgeNode } from '../nodes/TextJudgeNode'
import { VideoJudgeNode } from '../nodes/VideoJudgeNode'
import { isValidSocketConnection } from '../nodes/socketTypes'
import { activeGraphStore, useActiveGraphStore } from '../store/activeTab'
import { useTheme } from '../theme/ThemeProvider'

const NODE_TYPES = {
  peanut_source: PeanutSourceNode,
  dataset: DatasetNode,
  preprocessing: PreprocessingNode,
  lm_engine: LMEngineNode,
  judge_text: TextJudgeNode,
  judge_video: VideoJudgeNode,
  eval: EvalNode,
}

export function GraphCanvas() {
  const { theme } = useTheme()
  const nodes = useActiveGraphStore((s) => s.nodes)
  const edges = useActiveGraphStore((s) => s.edges)
  const onNodesChange = useActiveGraphStore((s) => s.onNodesChange)
  const onEdgesChange = useActiveGraphStore((s) => s.onEdgesChange)
  const onConnect = useActiveGraphStore((s) => s.onConnect)
  const selectNode = useActiveGraphStore((s) => s.selectNode)
  const openSecondaryTab = useActiveGraphStore((s) => s.openSecondaryTab)

  const checkValidConnection = (connection: Connection | Edge): boolean => {
    const nodesNow = activeGraphStore().getState().nodes
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
