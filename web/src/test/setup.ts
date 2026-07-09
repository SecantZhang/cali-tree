import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { useTabsStore } from '../store/tabsStore'

// Without vitest's `globals: true`, testing-library's auto-cleanup-on-afterEach
// never registers, so each test would leak its rendered DOM into the next one.
afterEach(() => {
  cleanup()
})

// useTabsStore is a module-level singleton (zustand) that persists across `it()` blocks in
// the same test file — reset it so each test's App mount creates exactly one fresh blank
// tab (see App.tsx's bootstrap effect) instead of accumulating tabs across tests.
afterEach(() => {
  useTabsStore.setState({ tabs: [], activeTabId: null })
})

// jsdom doesn't implement ResizeObserver, which @xyflow/react needs internally.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
// eslint-disable-next-line @typescript-eslint/no-explicit-any
;(globalThis as any).ResizeObserver ??= ResizeObserverStub
