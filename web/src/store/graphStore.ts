import {
  applyEdgeChanges,
  applyNodeChanges,
  type Connection,
  type Edge,
  type EdgeChange,
  type Node,
  type NodeChange,
} from '@xyflow/react'
import { create } from 'zustand'
import { defaultParamsFor } from '../nodes/paramSchemas'
import { isValidSocketConnection } from '../nodes/socketTypes'
import type { VeNodeData } from '../nodes/types'

// The wire format shared with the backend (server/schemas.py's GraphIn) — deliberately
// carries no layout info; canvas positions are a frontend-only concern.
export interface GraphNodeSpec {
  id: string
  type: string
  params: Record<string, unknown>
}
export interface GraphEdgeSpec {
  source: string
  source_socket: string
  target: string
  target_socket: string
}
export interface GraphSpecJSON {
  nodes: GraphNodeSpec[]
  edges: GraphEdgeSpec[]
}

export type VeNode = Node<VeNodeData>

interface GraphState {
  nodes: VeNode[]
  edges: Edge[]
  selectedNodeId: string | null
  secondaryTabNodeId: string | null
  onNodesChange: (changes: NodeChange<VeNode>[]) => void
  onEdgesChange: (changes: EdgeChange[]) => void
  onConnect: (connection: Connection) => void
  addNode: (type: string, position: { x: number; y: number }) => void
  updateNodeParams: (id: string, params: Record<string, unknown>) => void
  toggleNodeCollapsed: (id: string) => void
  removeNode: (id: string) => void
  selectNode: (id: string | null) => void
  openSecondaryTab: (id: string) => void
  closeSecondaryTab: () => void
  setNodeStatus: (id: string, status: VeNodeData['status'], error?: string | null) => void
  resetAllStatuses: () => void
  toJSON: () => GraphSpecJSON
  loadGraph: (graph: GraphSpecJSON) => void
}

let idCounter = 0
function nextId(type: string): string {
  idCounter += 1
  return `${type}-${idCounter}`
}

function edgeId(e: Pick<GraphEdgeSpec, 'source' | 'source_socket' | 'target' | 'target_socket'>) {
  return `${e.source}:${e.source_socket}->${e.target}:${e.target_socket}`
}

export const useGraphStore = create<GraphState>((set, get) => ({
  nodes: [],
  edges: [],
  selectedNodeId: null,
  secondaryTabNodeId: null,

  onNodesChange: (changes) => set({ nodes: applyNodeChanges(changes, get().nodes) }),
  onEdgesChange: (changes) => set({ edges: applyEdgeChanges(changes, get().edges) }),

  onConnect: (connection) => {
    const { nodes, edges } = get()
    const sourceType = nodes.find((n) => n.id === connection.source)?.type
    const targetType = nodes.find((n) => n.id === connection.target)?.type
    if (
      !isValidSocketConnection(
        sourceType, connection.sourceHandle, targetType, connection.targetHandle,
      )
    ) {
      return
    }
    // No fan-in: a new edge into a target socket replaces any existing one there.
    const withoutConflicting = edges.filter(
      (e) => !(e.target === connection.target && e.targetHandle === connection.targetHandle),
    )
    const newEdge: Edge = {
      id: edgeId({
        source: connection.source, source_socket: connection.sourceHandle ?? '',
        target: connection.target, target_socket: connection.targetHandle ?? '',
      }),
      source: connection.source,
      sourceHandle: connection.sourceHandle,
      target: connection.target,
      targetHandle: connection.targetHandle,
    }
    set({ edges: [...withoutConflicting, newEdge] })
  },

  addNode: (type, position) => {
    const id = nextId(type)
    const node: VeNode = {
      id, type, position,
      data: { params: defaultParamsFor(type), status: 'idle' },
    }
    set({ nodes: [...get().nodes, node], selectedNodeId: id })
  },

  updateNodeParams: (id, params) => {
    set({
      nodes: get().nodes.map((n) =>
        n.id === id ? { ...n, data: { ...n.data, params: { ...n.data.params, ...params } } } : n,
      ),
    })
  },

  toggleNodeCollapsed: (id) => {
    set({
      nodes: get().nodes.map((n) =>
        n.id === id ? { ...n, data: { ...n.data, collapsed: !n.data.collapsed } } : n,
      ),
    })
  },

  removeNode: (id) => {
    const { selectedNodeId } = get()
    set({
      nodes: get().nodes.filter((n) => n.id !== id),
      edges: get().edges.filter((e) => e.source !== id && e.target !== id),
      selectedNodeId: selectedNodeId === id ? null : selectedNodeId,
    })
  },

  selectNode: (id) => set({ selectedNodeId: id }),

  openSecondaryTab: (id) => set({ secondaryTabNodeId: id }),
  closeSecondaryTab: () => set({ secondaryTabNodeId: null }),

  setNodeStatus: (id, status, error = null) => {
    set({
      nodes: get().nodes.map((n) =>
        n.id === id ? { ...n, data: { ...n.data, status, error } } : n,
      ),
    })
  },

  resetAllStatuses: () => {
    set({ nodes: get().nodes.map((n) => ({ ...n, data: { ...n.data, status: 'idle', error: null } })) })
  },

  toJSON: () => {
    const { nodes, edges } = get()
    return {
      nodes: nodes.map((n) => ({ id: n.id, type: n.type ?? '', params: n.data.params })),
      edges: edges.map((e) => ({
        source: e.source,
        source_socket: e.sourceHandle ?? '',
        target: e.target,
        target_socket: e.targetHandle ?? '',
      })),
    }
  },

  loadGraph: (graph) => {
    set({
      nodes: graph.nodes.map((n, i) => ({
        id: n.id,
        type: n.type,
        position: { x: 80 + (i % 4) * 240, y: 80 + Math.floor(i / 4) * 180 },
        data: { params: n.params, status: 'idle' },
      })),
      edges: graph.edges.map((e) => ({
        id: edgeId(e),
        source: e.source,
        sourceHandle: e.source_socket,
        target: e.target,
        targetHandle: e.target_socket,
      })),
      selectedNodeId: null,
    })
  },
}))
