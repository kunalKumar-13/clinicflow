import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './styles.css'

const DEPARTMENTS = [
  'General Medicine',
  'Cardiology',
  'Dermatology',
  'Orthopaedics',
  'Paediatrics',
  'ENT',
]
const STATUSES = ['scheduled', 'completed', 'cancelled', 'no_show']
const LABEL = { scheduled: 'Scheduled', completed: 'Completed', cancelled: 'Cancelled', no_show: 'No show' }

const api = async (path, options = {}) => {
  const res = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (res.status === 204) return null
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(body.detail || `Request failed (${res.status})`)
  return body
}

const fmtTime = (iso) =>
  new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
const fmtDate = (iso) =>
  new Date(iso).toLocaleDateString([], { day: '2-digit', month: 'short', year: 'numeric' })

/* ------------------------------------------------------------------ */

function StatCard({ label, value, hint, accent }) {
  return (
    <div className="card stat">
      <span className="stat-label">{label}</span>
      <span className="stat-value" style={accent ? { color: accent } : undefined}>
        {value}
      </span>
      {hint && <span className="stat-hint">{hint}</span>}
    </div>
  )
}

function BookingModal({ onClose, onSaved }) {
  const [form, setForm] = useState({
    patient_name: '',
    patient_phone: '',
    doctor: '',
    department: DEPARTMENTS[0],
    scheduled_at: '',
    duration_minutes: 30,
    reason: '',
  })
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      await api('/appointments', {
        method: 'POST',
        body: JSON.stringify({ ...form, duration_minutes: Number(form.duration_minutes) }),
      })
      onSaved()
      onClose()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <header className="modal-head">
          <h2>Book an appointment</h2>
          <button className="icon-btn" onClick={onClose} aria-label="Close">x</button>
        </header>

        <form onSubmit={submit} className="modal-body">
          <label>
            Patient name
            <input required value={form.patient_name} onChange={set('patient_name')} placeholder="Ananya Rao" />
          </label>
          <label>
            Phone
            <input required value={form.patient_phone} onChange={set('patient_phone')} placeholder="9876543210" />
          </label>
          <label>
            Doctor
            <input required value={form.doctor} onChange={set('doctor')} placeholder="Dr. Mehta" />
          </label>
          <label>
            Department
            <select value={form.department} onChange={set('department')}>
              {DEPARTMENTS.map((d) => <option key={d}>{d}</option>)}
            </select>
          </label>
          <label>
            Date and time
            <input required type="datetime-local" value={form.scheduled_at} onChange={set('scheduled_at')} />
          </label>
          <label>
            Duration (minutes)
            <input type="number" min="10" max="240" step="5" value={form.duration_minutes} onChange={set('duration_minutes')} />
          </label>
          <label className="span-2">
            Reason
            <input value={form.reason} onChange={set('reason')} placeholder="Routine follow-up" />
          </label>

          {error && <p className="form-error span-2">{error}</p>}

          <div className="modal-actions span-2">
            <button type="button" className="btn ghost" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn primary" disabled={saving}>
              {saving ? 'Booking...' : 'Book appointment'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */

function App() {
  const [appointments, setAppointments] = useState([])
  const [stats, setStats] = useState(null)
  const [filter, setFilter] = useState('all')
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [build, setBuild] = useState(null)

  // Which build is serving us. Shown in the sidebar, so after a deployment you
  // can see the new commit has actually reached the running pods.
  useEffect(() => {
    api('/meta').then(setBuild).catch(() => setBuild(null))
  }, [])

  const load = useCallback(async () => {
    setError(null)
    try {
      const [list, s] = await Promise.all([
        api('/appointments'),
        api('/appointments/stats'),
      ])
      setAppointments(list)
      setStats(s)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const changeStatus = async (id, status) => {
    try {
      await api(`/appointments/${id}`, { method: 'PUT', body: JSON.stringify({ status }) })
      load()
    } catch (err) { setError(err.message) }
  }

  const remove = async (id) => {
    try {
      await api(`/appointments/${id}`, { method: 'DELETE' })
      load()
    } catch (err) { setError(err.message) }
  }

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase()
    return appointments
      .filter((a) => filter === 'all' || a.status === filter)
      .filter((a) => !q || a.patient_name.toLowerCase().includes(q) || a.doctor.toLowerCase().includes(q))
  }, [appointments, filter, query])

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">CF</span>
          <div>
            <strong>ClinicFlow</strong>
            <small>Appointment desk</small>
          </div>
        </div>

        <nav>
          <a className="nav-item active" href="#dashboard">Dashboard</a>
          <a className="nav-item" href="#appointments">Appointments</a>
          <a className="nav-item" href="#doctors">Doctors</a>
          <a className="nav-item" href="#departments">Departments</a>
        </nav>

        <div className="sidebar-foot">
          <div className="health">
            <span className={`dot ${error ? 'bad' : 'good'}`} />
            {error ? 'Backend unreachable' : 'Backend healthy'}
          </div>
          {build && (
            <dl className="build">
              <dt>Version</dt><dd>v{build.version}</dd>
              <dt>Commit</dt><dd className="mono">{build.commit}</dd>
              <dt>Running on</dt><dd>{build.environment}</dd>
              <dt>Host</dt><dd className="mono">{window.location.host}</dd>
            </dl>
          )}
        </div>
      </aside>

      <main className="content">
        <header className="topbar">
          <div>
            <h1>Today at the clinic</h1>
            <p className="muted">{fmtDate(new Date().toISOString())}</p>
          </div>
          <button className="btn primary" onClick={() => setModalOpen(true)}>+ New appointment</button>
        </header>

        {error && (
          <div className="banner error">
            <strong>Could not reach the API.</strong> {error}
            <button className="btn ghost small" onClick={load}>Retry</button>
          </div>
        )}

        <section className="stats">
          <StatCard label="Today" value={stats?.today ?? '-'} hint="appointments booked" />
          <StatCard label="Scheduled" value={stats?.scheduled ?? '-'} accent="#cba6f7" />
          <StatCard label="Completed" value={stats?.completed ?? '-'} accent="#a6e3a1" />
          <StatCard label="Cancelled" value={stats?.cancelled ?? '-'} accent="#f38ba8" />
          <StatCard
            label="Chair time today"
            value={stats ? `${Math.round((stats.booked_minutes_today / 60) * 10) / 10}h` : '-'}
            hint={stats?.busiest_doctor ? `Busiest: ${stats.busiest_doctor}` : null}
          />
        </section>

        <section className="card table-card">
          <div className="table-head">
            <div className="filters">
              <button className={`chip ${filter === 'all' ? 'on' : ''}`} onClick={() => setFilter('all')}>
                All ({appointments.length})
              </button>
              {STATUSES.map((s) => (
                <button key={s} className={`chip ${filter === s ? 'on' : ''}`} onClick={() => setFilter(s)}>
                  {LABEL[s]}
                </button>
              ))}
            </div>
            <input
              className="search"
              placeholder="Search patient or doctor"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>

          {loading ? (
            <p className="empty">Loading appointments...</p>
          ) : visible.length === 0 ? (
            <p className="empty">
              No appointments match this view. Use <b>+ New appointment</b> to book one.
            </p>
          ) : (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Patient</th><th>Doctor</th><th>Department</th>
                    <th>When</th><th>Length</th><th>Status</th><th></th>
                  </tr>
                </thead>
                <tbody>
                  {visible.map((a) => (
                    <tr key={a.id}>
                      <td>
                        <strong>{a.patient_name}</strong>
                        <small className="muted block">{a.patient_phone}</small>
                      </td>
                      <td>{a.doctor}</td>
                      <td><span className="dept">{a.department}</span></td>
                      <td>
                        {fmtDate(a.scheduled_at)}
                        <small className="muted block">{fmtTime(a.scheduled_at)}</small>
                      </td>
                      <td>{a.duration_minutes}m</td>
                      <td><span className={`badge ${a.status}`}>{LABEL[a.status]}</span></td>
                      <td className="row-actions">
                        <select
                          value={a.status}
                          onChange={(e) => changeStatus(a.id, e.target.value)}
                          aria-label={`Change status for ${a.patient_name}`}
                        >
                          {STATUSES.map((s) => <option key={s} value={s}>{LABEL[s]}</option>)}
                        </select>
                        <button className="icon-btn danger" onClick={() => remove(a.id)} aria-label="Delete">x</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </main>

      {modalOpen && <BookingModal onClose={() => setModalOpen(false)} onSaved={load} />}
    </div>
  )
}

createRoot(document.getElementById('root')).render(<App />)
