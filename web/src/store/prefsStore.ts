import { create } from 'zustand'
import { persist } from 'zustand/middleware'

// Panel sizes are a global app preference (like the theme), not per-workflow-tab —
// resizing a panel in one tab affects how every tab looks, and it survives a refresh.
const LEFT_MIN = 180
const LEFT_MAX = 480
const RIGHT_MIN = 220
const RIGHT_MAX = 480
const BOTTOM_MIN = 80
const BOTTOM_MAX = 480

function clamp(v: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, v))
}

interface PrefsState {
  leftWidth: number
  rightWidth: number
  bottomHeight: number
  leftCollapsed: boolean
  setLeftWidth: (w: number) => void
  setRightWidth: (w: number) => void
  setBottomHeight: (h: number) => void
  setLeftCollapsed: (collapsed: boolean) => void
}

export const usePrefsStore = create<PrefsState>()(
  persist(
    (set) => ({
      leftWidth: 260,
      rightWidth: 300,
      bottomHeight: 180,
      leftCollapsed: false,
      setLeftWidth: (w) => set({ leftWidth: clamp(w, LEFT_MIN, LEFT_MAX) }),
      setRightWidth: (w) => set({ rightWidth: clamp(w, RIGHT_MIN, RIGHT_MAX) }),
      setBottomHeight: (h) => set({ bottomHeight: clamp(h, BOTTOM_MIN, BOTTOM_MAX) }),
      setLeftCollapsed: (collapsed) => set({ leftCollapsed: collapsed }),
    }),
    { name: 'vejudge-panel-prefs' },
  ),
)
