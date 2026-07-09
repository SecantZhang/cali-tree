import {
  Background,
  Controls,
  MiniMap,
  PanOnScrollMode,
  ReactFlow,
  type Connection,
  type Edge,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { DatasetNode } from '../nodes/DatasetNode'
import { EvalTextNode } from '../nodes/EvalTextNode'
import { EvalVideoNode } from '../nodes/EvalVideoNode'
import { LMEngineNode } from '../nodes/LMEngineNode'
import { PeanutSourceNode } from '../nodes/PeanutSourceNode'
import { PreprocessingNode } from '../nodes/PreprocessingNode'
import { TextJudgeNode } from '../nodes/TextJudgeNode'
import { VideoJudgeNode } from '../nodes/VideoJudgeNode'
import { isValidSocketConnection } from '../nodes/socketTypes'
import { activeGraphStore, useActiveGraphStore } from '../store/activeTab'
import { usePrefsStore } from '../store/prefsStore'
import { useTheme } from '../theme/ThemeProvider'

const NODE_TYPES = {
  peanut_source: PeanutSourceNode,
  dataset: DatasetNode,
  preprocessing: PreprocessingNode,
  lm_engine: LMEngineNode,
  judge_text: TextJudgeNode,
  judge_video: VideoJudgeNode,
  eval_text: EvalTextNode,
  eval_video: EvalVideoNode,
}

export function GraphCanvas() {
  const { theme } = useTheme()
  const panOnScroll = usePrefsStore((s) => s.panOnScroll)
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
  )
}
