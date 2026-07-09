import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { useTabsStore } from '../store/tabsStore'

// One afterEach, ordered on purpose: unmount first, THEN reset the tabs singleton.
// - cleanup(): without vitest's `globals: true`, testing-library's auto-cleanup never
//   registers, so each test would leak its rendered DOM into the next one.
// - reset useTabsStore (a module-level zustand singleton that persists across `it()` blocks)
//   so each test's App mount creates exactly one fresh blank tab (see App.tsx's bootstrap
//   effect) instead of accumulating tabs across tests.
// These must be one hook, not two: vitest runs separate afterEach hooks in LIFO order, so a
// reset registered after cleanup would actually run *first* — nulling the active tab while a
// directly-rendered component (e.g. a secondary-tab component test) is still mounted, which
// re-renders it against no active tab and throws from useActive*Store.
afterEach(() => {
  cleanup()
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
