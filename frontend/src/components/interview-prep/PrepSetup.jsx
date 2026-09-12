export default function PrepSetup({ type, setType, budget, setBudget, custom, setCustom, sameDay,
  available, setAvailable, sameDayLimit, valid, busy, hasPlan, onSubmit }) {
  return (
    <form className="card prep-setup" onSubmit={onSubmit}>
      <h2>Your preparation, at your pace</h2>
      <p>Choose your focus and the time you can realistically set aside.</p>
      <label className="field">
        <span>Interview type</span>
        <select value={type} onChange={(e) => setType(e.target.value)} disabled={busy}>
          <option value="technical">Technical</option>
          <option value="behavioral">Behavioral</option>
          <option value="not_sure">Not sure — prepare for both</option>
        </select>
      </label>
      <label className="field">
        <span>Daily preparation time</span>
        <select value={budget} onChange={(e) => setBudget(e.target.value)} disabled={busy}>
          <option value="">Choose your time budget</option>
          <option value="30">30 minutes</option>
          <option value="60">1 hour</option>
          <option value="120">2 hours</option>
          <option value="custom">Custom</option>
        </select>
      </label>
      {budget === 'custom' && <label className="field">
        <span>Minutes per day</span>
        <input aria-label="Minutes per day" type="number" min="15" max="480" step="1" value={custom}
          onChange={(e) => setCustom(e.target.value)} required disabled={busy} />
        <small>Choose between 15 and 480 minutes.</small>
      </label>}
      {sameDay && <label className="field">
        <span>Minutes available before today's interview</span>
        <input aria-label="Minutes available before today's interview" type="number" min="1" max={sameDayLimit} step="1" value={available}
          onChange={(e) => setAvailable(e.target.value)} required disabled={busy} />
        <small>Enter 1–{sameDayLimit} minutes, within your daily budget and the time left before the interview.</small>
      </label>}
      <button className="btn primary" type="submit" disabled={!valid || busy}>
        {busy ? 'Building your checklist…' : hasPlan ? 'Update preparation plan' : 'Create my checklist'}
      </button>
      <p className="fine-print">Your checklist stays here. Only the interview belongs on your calendar.</p>
    </form>
  )
}
