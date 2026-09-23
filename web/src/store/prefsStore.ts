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
const MODAL_WIDTH_MIN = 500
const MODAL_WIDTH_MAX = 1800
const MODAL_HEIGHT_MIN = 400
const MODAL_HEIGHT_MAX = 1000

function clamp(v: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, v))
}

interface PrefsState {
  leftWidth: number
  rightWidth: number
  bottomHeight: number
  leftCollapsed: boolean
  // Secondary-tab modal size (SecondaryTabModal.tsx) — persists like every other
  // resizable surface in this app, so a resize sticks across reopens/reloads.
  modalWidth: number
  modalHeight: number
  // Two-finger trackpad scroll pans the canvas by default (GraphCanvas.tsx) rather than
  // zooming it — pinch/Ctrl+scroll still zoom regardless of this setting.
  panOnScroll: boolean
  setLeftWidth: (w: number) => void
  setRightWidth: (w: number) => void
  setBottomHeight: (h: number) => void
  setLeftCollapsed: (collapsed: boolean) => void
  setModalWidth: (w: number) => void
  setModalHeight: (h: number) => void
  setPanOnScroll: (v: boolean) => void
}

export const usePrefsStore = create<PrefsState>()(
  persist(
    (set) => ({
      leftWidth: 260,
      rightWidth: 300,
      bottomHeight: 180,
      leftCollapsed: false,
      modalWidth: 1200,
      modalHeight: 780,
      panOnScroll: true,
      setLeftWidth: (w) => set({ leftWidth: clamp(w, LEFT_MIN, LEFT_MAX) }),
      setRightWidth: (w) => set({ rightWidth: clamp(w, RIGHT_MIN, RIGHT_MAX) }),
      setBottomHeight: (h) => set({ bottomHeight: clamp(h, BOTTOM_MIN, BOTTOM_MAX) }),
      setLeftCollapsed: (collapsed) => set({ leftCollapsed: collapsed }),
      setModalWidth: (w) => set({ modalWidth: clamp(w, MODAL_WIDTH_MIN, MODAL_WIDTH_MAX) }),
      setModalHeight: (h) => set({ modalHeight: clamp(h, MODAL_HEIGHT_MIN, MODAL_HEIGHT_MAX) }),
      setPanOnScroll: (v) => set({ panOnScroll: v }),
    }),
    { name: 'vejudge-panel-prefs' },
  ),
)
