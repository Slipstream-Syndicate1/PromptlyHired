/**
 * When the install banner may show again.
 *
 * It is offered on every sign-in until the app is actually installed, because
 * an app on the home screen is the whole point of a PWA. "Not now" only hides
 * it for the rest of that session, so nobody is nagged twice in one sitting.
 */

export const INSTALLED = 'installed'

/**
 * Whether the banner should stay hidden.
 *
 * `stored` is the long-lived value: INSTALLED once the app is installed, and
 * anything else (nothing, or an old "not now" timestamp from the previous
 * behaviour) means it may show. `dismissedThisSession` is this sitting's
 * "Not now".
 */
export function isHidden(stored, dismissedThisSession = false) {
  return stored === INSTALLED || Boolean(dismissedThisSession)
}

/**
 * Whether a stored value only hides the banner because the app was installed.
 *
 * Uninstalling does not clear browser storage, so that value would hide the
 * banner forever. The browser fires its install event only when the app is not
 * installed, which is the moment to forget it.
 */
export function hiddenOnlyBecauseInstalled(stored) {
  return stored === INSTALLED
}

// "Not now" lasts for this sitting only; signing in again offers it once more.
export const SESSION_KEY = 'jobtrail.install_dismissed_session'

export function dismissedThisSession() {
  try {
    return sessionStorage.getItem(SESSION_KEY) === '1'
  } catch {
    return false
  }
}

export function dismissForThisSession() {
  try {
    sessionStorage.setItem(SESSION_KEY, '1')
  } catch {
    /* ignore: the banner just stays until the page is left */
  }
}

/** Called on sign-in, so the offer comes back until the app is installed. */
export function clearInstallDismissal() {
  try {
    sessionStorage.removeItem(SESSION_KEY)
  } catch {
    /* ignore */
  }
}
