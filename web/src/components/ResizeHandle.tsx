import { useCallback, useRef } from 'react'

/**
 * A thin drag handle between two panels. Reports each mouse-move as a delta (not an
 * absolute position) — the caller adds it to whatever it considers the current size,
 * read fresh from the store at drag time rather than a possibly-stale closed-over value.
 */
export function ResizeHandle({
  orientation, onResize,
}: {
  orientation: 'vertical' | 'horizontal'
  onResize: (delta: number) => void
}) {
  const draggingRef = useRef(false)
  const lastPosRef = useRef(0)

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault()
      draggingRef.current = true
      lastPosRef.current = orientation === 'vertical' ? e.clientX : e.clientY
      // .left-panel/.right-panel/.bottom-panel have a width/height CSS transition for
      // the collapse/expand toggle — without suppressing it here too, every resize step
      // during a live drag would animate instead of tracking the mouse instantly,
      // making the panel visibly lag behind the cursor.
      document.body.classList.add('is-resizing')

      const handleMouseMove = (ev: MouseEvent) => {
        if (!draggingRef.current) return
        const pos = orientation === 'vertical' ? ev.clientX : ev.clientY
        const delta = pos - lastPosRef.current
        lastPosRef.current = pos
        onResize(delta)
      }
      const handleMouseUp = () => {
        draggingRef.current = false
        document.body.classList.remove('is-resizing')
        window.removeEventListener('mousemove', handleMouseMove)
        window.removeEventListener('mouseup', handleMouseUp)
      }
      window.addEventListener('mousemove', handleMouseMove)
      window.addEventListener('mouseup', handleMouseUp)
    },
    [orientation, onResize],
  )

  return (
    <div
      className={`resize-handle resize-handle-${orientation}`}
      onMouseDown={handleMouseDown}
      role="separator"
      aria-orientation={orientation === 'vertical' ? 'vertical' : 'horizontal'}
    />
  )
}
