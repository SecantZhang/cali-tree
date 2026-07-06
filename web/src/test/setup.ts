import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { useGraphStore } from '../store/graphStore'
import { useRunStore } from '../store/runStore'

// Without vitest's `globals: true`, testing-library's auto-cleanup-on-afterEach
// never registers, so each test would leak its rendered DOM into the next one.
afterEach(() => {
  cleanup()
})

// useGraphStore/useRunStore are module-level singletons (zustand), so they persist
// across `it()` blocks in the same test file unless explicitly reset.
afterEach(() => {
  useGraphStore.setState({
    nodes: [], edges: [], selectedNodeId: null, secondaryTabNodeId: null,
  })
  useRunStore.getState().reset()
})

// jsdom doesn't implement ResizeObserver, which @xyflow/react needs internally.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
// eslint-disable-next-line @typescript-eslint/no-explicit-any
;(globalThis as any).ResizeObserver ??= ResizeObserverStub
