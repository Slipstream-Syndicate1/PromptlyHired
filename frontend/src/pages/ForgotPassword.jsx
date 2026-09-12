import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'

export default function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [sentMessage, setSentMessage] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const response = await api.forgotPassword(email)
      setSentMessage(response.detail)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth">
      <form className="auth-card" onSubmit={submit}>
        <h1>Reset your password</h1>

        {sentMessage ? (
          <>
            <div className="alert info">{sentMessage}</div>
            <p className="sub">
              Check your inbox and your spam folder. Nothing arrived?{' '}
              <button type="button" className="btn link" onClick={() => setSentMessage('')}>
                Send another link
              </button>
            </p>
          </>
        ) : (
          <>
            <p className="sub">
              Enter the email you signed up with and we will send you a link to choose a
              new password.
            </p>

            {error && <div className="alert error">{error}</div>}

            <label className="field">
              <span>Email</span>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                autoFocus
                required
              />
            </label>

            <button className="btn primary block" type="submit" disabled={busy}>
              {busy ? 'Sending…' : 'Send reset link'}
            </button>
          </>
        )}

        <p className="sub" style={{ marginTop: 16, marginBottom: 0 }}>
          <Link to="/login">Back to sign in</Link>
        </p>
      </form>
    </div>
  )
}
