import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import './ConfirmDialog.css'

/**
 * A confirmation for something that cannot be undone, over a dimmed page.
 *
 * The user types the phrase before the confirm button works, so deleting is a
 * deliberate act rather than a reflex click on a browser prompt. Like the job
 * dialog, it traps focus, closes on Escape or a click on the background, and
 * hands focus back to whatever opened it.
 */

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select, textarea, [tabindex]:not([tabindex="-1"])'

export default function ConfirmDialog({
  title,
  phrase,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  busy = false,
  onConfirm,
  onCancel,
  children,
}) {
  const [typed, setTyped] = useState('')
  const dialogRef = useRef(null)
  const inputRef = useRef(null)
  const onCancelRef = useRef(onCancel)
  useEffect(() => {
    onCancelRef.current = onCancel
  })

  // Spacing and capitals are not the point; typing the words is.
  const matches = typed.trim().toLowerCase() === phrase.toLowerCase()

  useEffect(() => {
    const previouslyFocused = document.activeElement
    inputRef.current?.focus()
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    const onKeyDown = (event) => {
      if (event.key === 'Escape') {
        event.stopPropagation()
        onCancelRef.current()
        return
      }
      if (event.key !== 'Tab' || !dialogRef.current) return
      const items = [...dialogRef.current.querySelectorAll(FOCUSABLE)].filter(
        (el) => el.offsetParent !== null,
      )
      if (items.length === 0) return
      const first = items[0]
      const last = items[items.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.body.style.overflow = previousOverflow
      previouslyFocused?.focus?.()
    }
  }, [])

  return createPortal(
    <div
      className="confirm-scrim"
      onClick={(event) => {
        if (event.target === event.currentTarget) onCancel()
      }}
    >
      <div
        className="confirm-dialog"
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
      >
        <h2 className="confirm-title" id="confirm-dialog-title">
          {title}
        </h2>
        <div className="confirm-body">{children}</div>

        <form
          onSubmit={(event) => {
            event.preventDefault()
            if (matches && !busy) onConfirm()
          }}
        >
          <label className="field">
            <span>
              Type <strong>{phrase}</strong> to confirm
            </span>
            <input
              ref={inputRef}
              value={typed}
              onChange={(event) => setTyped(event.target.value)}
              placeholder={phrase}
              autoComplete="off"
              spellCheck="false"
              aria-describedby="confirm-dialog-hint"
            />
          </label>
          <p className="fine-print" id="confirm-dialog-hint">
            This cannot be undone.
          </p>

          <div className="confirm-actions">
            <button className="btn" type="button" onClick={onCancel} disabled={busy}>
              {cancelLabel}
            </button>
            <button className="btn danger solid" type="submit" disabled={!matches || busy}>
              {busy ? 'Deleting…' : confirmLabel}
            </button>
          </div>
        </form>
      </div>
    </div>,
    document.body,
  )
}
