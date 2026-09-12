export default function PrepChecklist({ tasks, pending, onToggle, error }) {
  const complete = tasks.filter((task) => task.completed).length
  const days = tasks.reduce((groups, task) => {
    ;(groups[task.date] ??= []).push(task)
    return groups
  }, {})
  return (
    <section className="card prep-checklist" aria-label="Preparation checklist">
      <div className="prep-section-heading">
        <h2>Your daily checklist</h2>
        <span aria-live="polite">{complete} of {tasks.length} completed</span>
      </div>
      <progress value={complete} max={tasks.length || 1} aria-label="Preparation progress" />
      {error && <p className="alert error" role="alert">{error}</p>}
      {Object.entries(days).sort(([a], [b]) => a.localeCompare(b)).map(([date, items]) => (
        <section className="prep-day" key={date}>
          <h3><time dateTime={date}>{new Intl.DateTimeFormat(undefined, {
            weekday: 'long', month: 'short', day: 'numeric', timeZone: 'UTC',
          }).format(new Date(`${date}T12:00:00Z`))}</time>
            <span>{items.reduce((sum, task) => sum + task.minutes, 0)} min</span>
          </h3>
          {items.map((task) => <div className={`prep-task${task.completed ? ' is-complete' : ''}`} key={task.id}>
            <label>
              <input type="checkbox" checked={task.completed} disabled={pending.has(task.id)}
                onChange={() => onToggle(task)} />
              <strong>{task.title}</strong>
            </label>
            <div className="prep-task-body">
              <span className="chip">{task.category} · {task.minutes} min</span>
              <p>{task.instructions}</p>
              {task.outcome && <p><strong>Try this: </strong>{task.outcome}</p>}
            </div>
          </div>)}
        </section>
      ))}
    </section>
  )
}
