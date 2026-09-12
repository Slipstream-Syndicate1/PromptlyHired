/** Embed after the tracker successfully saves its canonical interview status. */
export default function InterviewPrepCTA({ status, startsAt, hasPlan = false, onOpen, onSchedule }) {
  if (status !== 'interview') return null
  return (
    <section className="card prep-callout" aria-label="Interview preparation">
      <div>
        <h2>Make time for your next step.</h2>
        <p>A focused preparation checklist, shaped around this role and your interview date.</p>
      </div>
      <button type="button" className="btn primary" onClick={startsAt ? onOpen : onSchedule}>
        {!startsAt ? 'Schedule interview' : hasPlan ? 'Continue preparation' : 'Prepare with AI'}
      </button>
    </section>
  )
}
