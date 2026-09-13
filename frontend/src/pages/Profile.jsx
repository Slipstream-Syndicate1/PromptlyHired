import { useEffect, useState } from 'react'
import { api } from '../api/client'
import AvatarUpload from '../components/AvatarUpload.jsx'
import ResumePanel from '../components/ResumePanel.jsx'
import { useAuth } from '../context/AuthContext.jsx'

export default function Profile() {
  const { user, setUser, logout } = useAuth()
  const [name, setName] = useState(user?.name ?? '')
  const [resume, setResume] = useState(null)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [preferredLocation, setPreferredLocation] = useState(user?.preferred_location ?? '')
  const [includeRemote, setIncludeRemote] = useState(user?.include_remote ?? true)
  const [prefsBusy, setPrefsBusy] = useState(false)

  useEffect(() => {
    api.getActiveResume().then(setResume).catch((err) => setError(err.message))
  }, [])

  const save = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    setMessage('')
    try {
      setUser(await api.updateProfile({ name }))
      setMessage('Saved.')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const savePreferences = async (event) => {
    event.preventDefault()
    setPrefsBusy(true)
    setError('')
    setMessage('')
    try {
      setUser(
        await api.updateProfile({
          preferred_location: preferredLocation.trim() || null,
          include_remote: includeRemote,
        }),
      )
      setMessage('Recommendation preferences saved.')
    } catch (err) {
      setError(err.message)
    } finally {
      setPrefsBusy(false)
    }
  }

  return (
    <main className="page profile-page">
      <div className="page-header">
        <h1>Profile</h1>
      </div>

      {error && <div className="alert error">{error}</div>}
      {message && <div className="alert info">{message}</div>}

      {/* Resume first: it is the thing the whole product is built around. */}
      <ResumePanel resume={resume} onChange={setResume} user={user} />

      <div className="card">
        <AvatarUpload user={user} onChange={setUser} />
      </div>

      <form className="card" onSubmit={save}>
        <label className="field">
          <span>Name</span>
          <input value={name} onChange={(e) => setName(e.target.value)} maxLength={120} />
        </label>
        <label className="field">
          <span>Email</span>
          <input value={user?.email ?? ''} disabled />
        </label>
        <button className="btn primary block" type="submit" disabled={busy}>
          {busy ? 'Saving…' : 'Save changes'}
        </button>
      </form>

      <form className="card" onSubmit={savePreferences}>
        <h2 className="section-title" style={{ marginTop: 0 }}>
          Job recommendations
        </h2>
        <p className="fine-print">
          Recommendations search for the job titles in your resume. Leave the location
          blank to use the one on your resume.
        </p>
        <label className="field">
          <span>Preferred location</span>
          <input
            value={preferredLocation}
            onChange={(e) => setPreferredLocation(e.target.value)}
            maxLength={120}
            placeholder="e.g. Calgary, AB"
          />
        </label>
        <label
          className="field"
          style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}
        >
          <input
            type="checkbox"
            checked={includeRemote}
            onChange={(e) => setIncludeRemote(e.target.checked)}
            style={{ width: 'auto', margin: 0 }}
          />
          <span style={{ margin: 0 }}>Include remote jobs</span>
        </label>
        <button className="btn primary block" type="submit" disabled={prefsBusy}>
          {prefsBusy ? 'Saving…' : 'Save preferences'}
        </button>
      </form>

      <button className="btn danger block" onClick={logout}>
        Sign out
      </button>
    </main>
  )
}
