import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { api, clearTokens, setTokens } from '../api/client'
import { clearInstallDismissal } from '../lib/installSnooze.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [booting, setBooting] = useState(true)

  // On load the access token is gone (memory only), so trade the stored
  // refresh token for a fresh one before deciding whether to show the app.
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      if (api.hasSession() && (await api.restoreSession())) {
        try {
          const profile = await api.me()
          if (!cancelled) setUser(profile)
        } catch {
          clearTokens()
        }
      }
      if (!cancelled) setBooting(false)
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const login = useCallback(async (email, password) => {
    setTokens(await api.login({ email, password }))
    // Signing in offers the install banner again, until the app is installed.
    clearInstallDismissal()
    setUser(await api.me())
  }, [])

  const signup = useCallback(async (name, email, password) => {
    setTokens(await api.signup({ name, email, password }))
    clearInstallDismissal()
    setUser(await api.me())
  }, [])

  // A successful reset returns a fresh session, so the user lands signed in.
  const resetPassword = useCallback(async (token, password) => {
    setTokens(await api.resetPassword(token, password))
    setUser(await api.me())
  }, [])

  const logout = useCallback(async () => {
    await api.logout()
    setUser(null)
  }, [])

  const value = useMemo(
    () => ({ user, setUser, booting, login, signup, resetPassword, logout }),
    [user, booting, login, signup, resetPassword, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
