import {
  applyEdgeChanges,
  applyNodeChanges,
  type Connection,
  type Edge,
  type EdgeChange,
  type Node,
  type NodeChange,
} from '@xyflow/react'
import { create, type StoreApi, type UseBoundStore } from 'zustand'
import { defaultParamsFor } from '../nodes/paramSchemas'
import { isValidSocketConnection } from '../nodes/socketTypes'
import type { VeNodeData } from '../nodes/types'

// The wire format shared with the backend (server/schemas.py's GraphIn). position/size
// (and the cosmetic view-state fields below) are wire-layer-only — never touched by graph
// execution — optional so older saved workflows without them still load fine.
export interface GraphNodeSpec {
  id: string
  type: string
  params: Record<string, unknown>
  position?: { x: number; y: number }
  size?: { width: number; height: number }
  // Purely cosmetic "where you left off" state, restored on load so reopening a workflow
  // looks the same as when it was saved — deliberately NOT a substitute for real run state
  // (which already has its own independent, more authoritative mechanism: each run is
  // tagged with `workflow_name` and discoverable via `GET /api/workflows/{name}/runs`,
  // which already drives the Resume button). `status` is sanitized on load (see
  // loadGraph) since "running" can never be genuinely true immediately after a fresh load.
  status?: VeNodeData['status']
  error?: string | null
  collapsed?: boolean
  expanded_size?: { width: number; height: number }
  // Mirrors `runStore.staleNodeIds` at save time (a separate store — graphStore has no
  // access to it directly, so callers of `toJSON` pass it in explicitly; see saveTab.ts).
  stale?: boolean
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

export interface GraphState {
  nodes: VeNode[]
  edges: Edge[]
  selectedNodeId: string | null
  secondaryTabNodeId: string | null
  // Which saved workflow (if any) is currently loaded — the tab-level source of truth is
  // tabsStore's own `workflowName` field; this mirrors it for components (Resume lookup,
  // Judge Node's `workflow_name` tag on run) that only have access to a GraphStoreApi.
  currentWorkflowName: string | null
  setCurrentWorkflowName: (name: string | null) => void
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
  // `staleNodeIds` comes from the tab's separate runStore (see saveTab.ts) — graphStore
  // itself has no access to it.
  toJSON: (staleNodeIds?: Set<string>) => GraphSpecJSON
  loadGraph: (graph: GraphSpecJSON) => void
}

export type GraphStoreApi = UseBoundStore<StoreApi<GraphState>>

function edgeId(e: Pick<GraphEdgeSpec, 'source' | 'source_socket' | 'target' | 'target_socket'>) {
  return `${e.source}:${e.source_socket}->${e.target}:${e.target_socket}`
}

/**
 * One graph document's worth of state — one instance per open tab (see tabsStore.ts).
 * `idCounter` lives in this closure (not module-level) so two tabs never collide on the
 * same generated node id.
 *
 * `onDirty` is called by every action that changes graph *content* (nodes/edges/params/
 * position/size) — deliberately not by `loadGraph` (that's the just-loaded *clean* state;
 * the caller marks the tab clean explicitly after calling it) or by pure UI/run-status
 * bookkeeping (`selectNode`, `openSecondaryTab`, `setNodeStatus`, `resetAllStatuses`).
 * An explicit flag, not a hash/diff: position/size changes fire many times per drag
 * gesture, and an idempotent `dirty = true` write is O(1) per call where hashing the whole
 * graph on every drag frame would not be.
 */
export function createGraphStore(onDirty: () => void): GraphStoreApi {
  let idCounter = 0
  function nextId(type: string): string {
    idCounter += 1
    return `${type}-${idCounter}`
  }

  return create<GraphState>((set, get) => ({
    nodes: [],
    edges: [],
    selectedNodeId: null,
    secondaryTabNodeId: null,
    currentWorkflowName: null,
    setCurrentWorkflowName: (name) => set({ currentWorkflowName: name }),

    onNodesChange: (changes) => {
      set({ nodes: applyNodeChanges(changes, get().nodes) })
      onDirty()
    },
    onEdgesChange: (changes) => {
      set({ edges: applyEdgeChanges(changes, get().edges) })
      onDirty()
    },

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
      onDirty()
    },

    addNode: (type, position) => {
      const id = nextId(type)
      const node: VeNode = {
        id, type, position,
        data: { params: defaultParamsFor(type), status: 'idle' },
      }
      set({ nodes: [...get().nodes, node], selectedNodeId: id })
      onDirty()
    },

    updateNodeParams: (id, params) => {
      set({
        nodes: get().nodes.map((n) =>
          n.id === id ? { ...n, data: { ...n.data, params: { ...n.data.params, ...params } } } : n,
        ),
      })
      onDirty()
    },

    toggleNodeCollapsed: (id) => {
      set({
        nodes: get().nodes.map((n) => {
          if (n.id !== id) return n
          const collapsed = !n.data.collapsed
          if (collapsed) {
            // Capture whatever explicit size the node currently has (a manual resize, or a
            // loaded workflow's saved `size`) before clearing it, so the node can shrink to
            // its one-line collapsed summary instead of staying pinned to that pixel size —
            // then restore it below on expand.
            const width = n.width ?? n.measured?.width
            const height = n.height ?? n.measured?.height
            return {
              ...n,
              width: undefined,
              height: undefined,
              data: {
                ...n.data,
                collapsed,
                ...(width != null && height != null ? { expandedSize: { width, height } } : {}),
              },
            }
          }
          const { expandedSize } = n.data
          return {
            ...n,
            ...(expandedSize ? { width: expandedSize.width, height: expandedSize.height } : {}),
            data: { ...n.data, collapsed },
          }
        }),
      })
      onDirty()
    },

    removeNode: (id) => {
      const { selectedNodeId } = get()
      set({
        nodes: get().nodes.filter((n) => n.id !== id),
        edges: get().edges.filter((e) => e.source !== id && e.target !== id),
        selectedNodeId: selectedNodeId === id ? null : selectedNodeId,
      })
      onDirty()
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

    toJSON: (staleNodeIds) => {
      const { nodes, edges } = get()
      return {
        nodes: nodes.map((n) => {
          const width = n.width ?? n.measured?.width
          const height = n.height ?? n.measured?.height
          return {
            id: n.id,
            type: n.type ?? '',
            params: n.data.params,
            position: n.position,
            ...(width != null && height != null ? { size: { width, height } } : {}),
            status: n.data.status,
            ...(n.data.error != null ? { error: n.data.error } : {}),
            ...(n.data.collapsed ? { collapsed: n.data.collapsed } : {}),
            ...(n.data.expandedSize ? { expanded_size: n.data.expandedSize } : {}),
            ...(staleNodeIds?.has(n.id) ? { stale: true } : {}),
          }
        }),
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
        nodes: graph.nodes.map((n, i) => {
          // "running" can never be genuinely true the instant a workflow is (re)loaded —
          // no run is actually in flight yet — so a stale "running" from whenever this was
          // last saved is sanitized back to "idle" rather than lying about live activity.
          const status = n.status && n.status !== 'running' ? n.status : 'idle'
          return {
            id: n.id,
            type: n.type,
            position: n.position ?? { x: 80 + (i % 4) * 240, y: 80 + Math.floor(i / 4) * 180 },
            ...(n.size ? { width: n.size.width, height: n.size.height } : {}),
            data: {
              params: n.params,
              status,
              ...(n.error != null ? { error: n.error } : {}),
              ...(n.collapsed ? { collapsed: n.collapsed } : {}),
              ...(n.expanded_size ? { expandedSize: n.expanded_size } : {}),
            },
          }
        }),
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
}
