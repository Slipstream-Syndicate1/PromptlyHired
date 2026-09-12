import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'

// bcrypt's limit, which the API enforces. Counted in bytes, not characters,
// because accented letters and emoji take more than one byte each.
const MAX_PASSWORD_BYTES = 72

export default function ResetPassword() {
  const [params] = useSearchParams()
  const token = params.get('token') || ''
  const { resetPassword } = useAuth()
  const navigate = useNavigate()
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (event) => {
    event.preventDefault()
    setError('')
    if (password.length < 8) {
      setError('Use at least 8 characters.')
      return
    }
    if (new TextEncoder().encode(password).length > MAX_PASSWORD_BYTES) {
      setError('That password is too long. Use 72 bytes or fewer.')
      return
    }
    if (password !== confirm) {
      setError('The two passwords do not match.')
      return
    }

    setBusy(true)
    try {
      await resetPassword(token, password)
      navigate('/', { replace: true })
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  if (!token) {
    return (
      <div className="auth">
        <div className="auth-card">
          <h1>Reset link incomplete</h1>
          <p className="sub">
            Open the link from your email again, or request a new one.
          </p>
          <Link className="btn primary block" to="/forgot-password">
            Request a new link
          </Link>
        </div>
      </div>
    )
  }

  const linkExpired = /invalid or has expired/i.test(error)

  return (
    <div className="auth">
      <form className="auth-card" onSubmit={submit}>
        <h1>Choose a new password</h1>
        <p className="sub">This signs you out on every other device and signs you in here.</p>

        {error && (
          <div className="alert error">
            {error}{' '}
            {linkExpired && <Link to="/forgot-password">Request a new link</Link>}
          </div>
        )}

        <label className="field">
          <span>New password</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
            minLength={8}
            autoFocus
            required
          />
        </label>

        <label className="field">
          <span>Confirm new password</span>
          <input
            type="password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            autoComplete="new-password"
            required
          />
        </label>

        <button className="btn primary block" type="submit" disabled={busy}>
          {busy ? 'Saving…' : 'Set new password'}
        </button>

        <p className="sub" style={{ marginTop: 16, marginBottom: 0 }}>
          <Link to="/login">Back to sign in</Link>
        </p>
      </form>
    </div>
  )
}
