/**
 * When the install banner may show again.
 *
 * "Not now" hides it for a few days rather than forever, so someone who was
 * busy gets asked once more later. Installing hides it for good.
 */

export const SNOOZE_DAYS = 3
export const INSTALLED = 'installed'
const DAY_MS = 24 * 60 * 60 * 1000

/**
 * Whether a stored value still hides the banner.
 *
 * The value is a timestamp (milliseconds) saying when "Not now" was tapped, or
 * INSTALLED. Anything else - nothing stored, or the old "1" that used to mean
 * "never again" - lets the banner show.
 */
export function isHidden(stored, now = Date.now()) {
  if (stored === INSTALLED) return true
  const dismissedAt = Number(stored)
  if (!Number.isFinite(dismissedAt) || dismissedAt <= 1) return false
  return now - dismissedAt < SNOOZE_DAYS * DAY_MS
}

export function snoozeValue(now = Date.now()) {
  return String(now)
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
