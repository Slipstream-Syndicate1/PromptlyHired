import { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'

/**
 * A small centred dialog. Escape and a click on the backdrop close it; focus
 * goes to the first field on open and returns to where it was on close.
 * Rendered in a portal so it isn't clipped by a scrolling board or a
 * transformed card.
 */
export default function Modal({ title, onClose, children }) {
  const panelRef = useRef(null)

  useEffect(() => {
    const previous = document.activeElement
    const first = panelRef.current?.querySelector('input, select, textarea, button')
    first?.focus()

    const onKey = (event) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
      previous?.focus?.()
    }
  }, [onClose])

  return createPortal(
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal-panel card" role="dialog" aria-modal="true" aria-label={title} ref={panelRef}>
        <div className="modal-head">
          <h2>{title}</h2>
          <button type="button" className="text-btn" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        {children}
      </div>
    </div>,
    document.body,
  )
}
