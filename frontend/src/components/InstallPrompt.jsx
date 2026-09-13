import { useEffect, useState } from 'react'
import { isIos, isStandalone } from '../api/platform'
import { INSTALLED, isHidden, snoozeValue } from '../lib/installSnooze.js'

// Kept from the original name so existing dismissals are read, not ignored.
const STORAGE_KEY = 'jobtrail.install_dismissed'

function readStored() {
  try {
    return localStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

function writeStored(value) {
  try {
    localStorage.setItem(STORAGE_KEY, value)
  } catch {
    /* private mode - the banner simply shows again next visit */
  }
}

/**
 * Offers to install the app on the home screen, where it opens full screen
 * like a regular app.
 *
 * Chrome, Edge and Android give a real `beforeinstallprompt` event, so they get
 * an Install button. Safari on iPhone and iPad gives nothing, so it gets the
 * manual steps instead. "Not now" hides the banner for a few days; installing
 * hides it for good.
 */
export default function InstallPrompt() {
  const [deferred, setDeferred] = useState(null)
  const [showIosHint, setShowIosHint] = useState(false)
  const [hidden, setHidden] = useState(() => isHidden(readStored()))

  useEffect(() => {
    if (isStandalone() || isHidden(readStored())) return

    const onBeforeInstall = (event) => {
      event.preventDefault()
      setDeferred(event)
    }
    const onInstalled = () => {
      writeStored(INSTALLED)
      setHidden(true)
    }
    window.addEventListener('beforeinstallprompt', onBeforeInstall)
    window.addEventListener('appinstalled', onInstalled)

    // Safari never fires the install event, so show the manual route instead.
    if (isIos()) setShowIosHint(true)

    return () => {
      window.removeEventListener('beforeinstallprompt', onBeforeInstall)
      window.removeEventListener('appinstalled', onInstalled)
    }
  }, [])

  const notNow = () => {
    writeStored(snoozeValue())
    setHidden(true)
  }

  const install = async () => {
    if (!deferred) return
    deferred.prompt()
    const { outcome } = await deferred.userChoice
    setDeferred(null)
    if (outcome === 'accepted') {
      writeStored(INSTALLED)
      setHidden(true)
    } else {
      // Cancelling the browser dialog counts as "Not now".
      notNow()
    }
  }

  if (hidden || isStandalone() || (!deferred && !showIosHint)) return null

  return (
    <div className="install-banner">
      <div className="job-main">
        <strong>Install PromptlyHired</strong>
        <p className="job-company" style={{ marginTop: 2 }}>
          {deferred
            ? 'Add it to your home screen to open it full screen, like a regular app.'
            : 'Tap Share, then “Add to Home Screen” to open it full screen, like a regular app.'}
        </p>
      </div>
      <div className="install-actions">
        {deferred && (
          <button className="btn primary" onClick={install}>
            Install
          </button>
        )}
        <button className="btn" onClick={notNow}>
          Not now
        </button>
      </div>
    </div>
  )
}
