import { useRef, useState } from 'react'

export default function PrepChat({ planId, initialMessages = [], sendMessage, disabled = false }) {
  const [messages, setMessages] = useState(initialMessages)
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const request = useRef(null)
  const inFlight = useRef(false)

  async function submit(event) {
    event.preventDefault()
    const text = draft.trim()
    if (!text || text.length > 2000 || inFlight.current || disabled) return
    inFlight.current = true
    setBusy(true)
    setError('')
    if (request.current?.message !== text) {
      request.current = { message: text, client_request_id: crypto.randomUUID() }
    }
    const submitted = request.current
    try {
      const response = await sendMessage(planId, submitted)
      setMessages((current) => [...current,
        { id: submitted.client_request_id, role: 'user', content: text }, response])
      setDraft('')
      request.current = null
    } catch (err) {
      setError(err.message || 'Could not send your question. Try again.')
    } finally {
      inFlight.current = false
      setBusy(false)
    }
  }

  return <section className="card prep-chat" aria-label="Interview preparation assistant">
    <h2>A little guidance, when you need it</h2>
    <p>Ask about a topic, practice question, or a story from your experience.</p>
    <div className="prep-messages" role="log" aria-label="Preparation conversation" aria-live="polite">
      {!messages.length && <p className="prep-chat-empty">Try “Help me practice the first task” or “How do I structure a STAR answer?”</p>}
      {messages.map((message) => <div key={message.id} className={`prep-message ${message.role === 'user' ? 'from-user' : ''}`}>
        <strong>{message.role === 'user' ? 'You' : 'Preparation guide'}</strong>
        <p>{message.content}</p>
      </div>)}
    </div>
    {error && <p className="alert error" role="alert">{error}</p>}
    <form onSubmit={submit}>
      <label className="field">
        <span>Ask about your preparation</span>
        <textarea rows={3} maxLength={2000} value={draft} disabled={busy || disabled}
          onChange={(e) => setDraft(e.target.value)} placeholder="What would you like to practice?" />
      </label>
      <button className="btn primary" type="submit" disabled={busy || disabled || !draft.trim()}>
        {busy ? 'Thinking…' : 'Send question'}
      </button>
      {busy && <span role="status"> Preparing your answer…</span>}
    </form>
    <p className="fine-print">Practice suggestions, not a prediction of the questions you will be asked.</p>
  </section>
}
