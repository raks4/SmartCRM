import { useEffect, useMemo, useState } from 'react'
import { authApi, leadApi } from './api'
import './App.css'

function App() {
  const [theme, setTheme] = useState('light')
  const [screen, setScreen] = useState('landing')
  const [user, setUser] = useState(null)
  const [authError, setAuthError] = useState('')
  const [busy, setBusy] = useState(false)
  const [leads, setLeads] = useState([])
  const [metrics, setMetrics] = useState({ total_value: 0, won_value: 0, conversion_rate: 0 })

  const [loginForm, setLoginForm] = useState({ username: '', password: '' })
  const [leadForm, setLeadForm] = useState({
    company_name: '',
    contact_name: '',
    contact_email: '',
    contact_phone: '',
    source: 'Website',
    stage: 'new',
    estimated_value: '',
    assigned_to: '',
    last_touch: '',
    notes: '',
  })

  useEffect(() => {
    const savedTheme = localStorage.getItem('smartcrm-theme')
    const initialTheme = savedTheme || 'light'
    setTheme(initialTheme)
    document.documentElement.setAttribute('data-theme', initialTheme)
  }, [])

  const toggleTheme = () => {
    const nextTheme = theme === 'light' ? 'dark' : 'light'
    setTheme(nextTheme)
    document.documentElement.setAttribute('data-theme', nextTheme)
    localStorage.setItem('smartcrm-theme', nextTheme)
  }

  const loadData = async () => {
    const [leadResponse, dashboardResponse] = await Promise.all([leadApi.list(), leadApi.dashboard()])
    setLeads(leadResponse.items || [])
    setMetrics(dashboardResponse.metrics || { total_value: 0, won_value: 0, conversion_rate: 0 })
  }

  useEffect(() => {
    const checkSession = async () => {
      try {
        const response = await authApi.session()
        setUser(response.user)
        setScreen('workspace')
        await loadData()
      } catch {
        setScreen('landing')
      }
    }

    checkSession()
  }, [])

  const pipeline = useMemo(() => {
    const byStage = leads.reduce((acc, lead) => {
      acc[lead.stage] = (acc[lead.stage] || 0) + 1
      return acc
    }, {})

    return [
      { label: 'New', key: 'new', value: byStage.new || 0 },
      { label: 'Qualified', key: 'qualified', value: byStage.qualified || 0 },
      { label: 'Proposal', key: 'proposal', value: byStage.proposal || 0 },
      { label: 'Negotiation', key: 'negotiation', value: byStage.negotiation || 0 },
      { label: 'Won', key: 'won', value: byStage.won || 0 },
      { label: 'Lost', key: 'lost', value: byStage.lost || 0 },
    ]
  }, [leads])

  const totalValue = useMemo(() => leads.reduce((sum, lead) => sum + Number(lead.estimated_value), 0), [leads])

  const wonValue = useMemo(() => leads.filter((lead) => lead.stage === 'won').reduce((sum, lead) => sum + Number(lead.estimated_value), 0), [leads])

  const conversionRate = leads.length ? Math.round((pipeline.find((item) => item.key === 'won').value / leads.length) * 100) : 0

  const toMoney = (amount) =>
    new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      maximumFractionDigits: 0,
    }).format(amount)

  const openLogin = () => {
    setScreen('login')
    setAuthError('')
  }

  const onLogin = async (event) => {
    event.preventDefault()
    setBusy(true)
    setAuthError('')
    try {
      const response = await authApi.login(loginForm)
      setUser(response.user)
      await loadData()
      setScreen('workspace')
    } catch (error) {
      setAuthError(error.message)
    } finally {
      setBusy(false)
    }
  }

  const onLogout = async () => {
    await authApi.logout()
    setUser(null)
    setLeads([])
    setScreen('landing')
    setLoginForm({ username: '', password: '' })
  }

  const onCreateLead = async (event) => {
    event.preventDefault()
    setBusy(true)
    try {
      await leadApi.create({
        ...leadForm,
        estimated_value: Number(leadForm.estimated_value || 0),
      })
      await loadData()
      setLeadForm({
        company_name: '',
        contact_name: '',
        contact_email: '',
        contact_phone: '',
        source: 'Website',
        stage: 'new',
        estimated_value: '',
        assigned_to: '',
        last_touch: '',
        notes: '',
      })
    } finally {
      setBusy(false)
    }
  }

  if (screen === 'landing') {
    return (
      <main className="crm">
        <header className="hero">
          <div className="hero-top">
            <p className="kicker">Smart CRM</p>
            <button className="theme-toggle" onClick={toggleTheme}>
              {theme === 'light' ? 'Dark mode' : 'Light mode'}
            </button>
          </div>
          <h1>Convert more leads with cleaner sales execution.</h1>
          <p className="sub">
            Track opportunities, conversations, and follow-up actions in one operational system.
          </p>
          <div className="hero-actions">
            <button className="cta" onClick={openLogin}>
              Log In
            </button>
            <span className="hint">Start from the landing page and move straight into your workspace.</span>
          </div>
        </header>

        <section className="stack two-col">
          <article className="panel">
            <h2>Sales Workspace</h2>
            <p className="muted-text">
              Pipeline cards, current leads, communication history, and reminders for daily execution.
            </p>
          </article>
          <article className="panel">
            <h2>Lead Intake Interface</h2>
            <p className="muted-text">
              A structured form to capture new lead inputs cleanly before the team starts follow-up.
            </p>
          </article>
        </section>
      </main>
    )
  }

  if (screen === 'login') {
    return (
      <main className="crm auth-wrap">
        <section className="panel auth-card">
          <p className="kicker">Smart CRM Access</p>
          <h1>Welcome back</h1>
          <p className="muted-text">Use your Django user credentials to enter the CRM workspace.</p>
          <form onSubmit={onLogin} className="form-grid">
            <label>
              Username
              <input
                value={loginForm.username}
                onChange={(event) => setLoginForm((prev) => ({ ...prev, username: event.target.value }))}
                placeholder="e.g. admin"
                required
              />
            </label>
            <label>
              Password
              <input
                value={loginForm.password}
                onChange={(event) => setLoginForm((prev) => ({ ...prev, password: event.target.value }))}
                placeholder="Your password"
                type="password"
                required
              />
            </label>
            {authError && <p className="error">{authError}</p>}
            <div className="row-actions">
              <button className="cta" disabled={busy} type="submit">
                {busy ? 'Signing in...' : 'Sign In'}
              </button>
              <button className="ghost" onClick={() => setScreen('landing')} type="button">
                Back
              </button>
            </div>
          </form>
        </section>
      </main>
    )
  }

  return (
    <main className="crm">
      <header className="hero">
        <div className="hero-top">
          <p className="kicker">Smart CRM</p>
          <div className="row-actions">
            <button className="theme-toggle" onClick={toggleTheme}>
              {theme === 'light' ? 'Dark mode' : 'Light mode'}
            </button>
            <button className="ghost light" onClick={onLogout}>
              Log Out ({user?.username})
            </button>
          </div>
        </div>
        <h1>Lead Tracking and Follow-Up Workspace</h1>
        <p className="sub">
          Capture leads from intake form, then manage them in the pipeline view with measurable conversion data.
        </p>
      </header>

      <section className="metrics">
        <article>
          <h2>Total Pipeline Value</h2>
          <p>{toMoney(metrics.total_value || totalValue)}</p>
        </article>
        <article>
          <h2>Won Revenue</h2>
          <p>{toMoney(metrics.won_value || wonValue)}</p>
        </article>
        <article>
          <h2>Conversion Rate</h2>
          <p>{metrics.conversion_rate || conversionRate}%</p>
        </article>
      </section>

      <section className="panel">
        <h2>Lead Pipeline</h2>
        <div className="pipeline-grid">
          {pipeline.map((item) => (
            <div key={item.label} className="pipeline-card">
              <span>{item.label}</span>
              <strong>{item.value}</strong>
            </div>
          ))}
        </div>
      </section>

      <section className="panel">
        <h2>Lead Intake Interface</h2>
        <form onSubmit={onCreateLead} className="form-grid">
          <label>
            Company Name
            <input
              required
              value={leadForm.company_name}
              onChange={(event) => setLeadForm((prev) => ({ ...prev, company_name: event.target.value }))}
            />
          </label>
          <label>
            Contact Name
            <input
              required
              value={leadForm.contact_name}
              onChange={(event) => setLeadForm((prev) => ({ ...prev, contact_name: event.target.value }))}
            />
          </label>
          <label>
            Contact Email
            <input
              type="email"
              value={leadForm.contact_email}
              onChange={(event) => setLeadForm((prev) => ({ ...prev, contact_email: event.target.value }))}
            />
          </label>
          <label>
            Contact Phone
            <input
              value={leadForm.contact_phone}
              onChange={(event) => setLeadForm((prev) => ({ ...prev, contact_phone: event.target.value }))}
            />
          </label>
          <label>
            Source
            <input
              value={leadForm.source}
              onChange={(event) => setLeadForm((prev) => ({ ...prev, source: event.target.value }))}
            />
          </label>
          <label>
            Assigned To
            <input
              value={leadForm.assigned_to}
              onChange={(event) => setLeadForm((prev) => ({ ...prev, assigned_to: event.target.value }))}
            />
          </label>
          <label>
            Stage
            <select
              value={leadForm.stage}
              onChange={(event) => setLeadForm((prev) => ({ ...prev, stage: event.target.value }))}
            >
              <option value="new">New</option>
              <option value="qualified">Qualified</option>
              <option value="proposal">Proposal</option>
              <option value="negotiation">Negotiation</option>
              <option value="won">Won</option>
              <option value="lost">Lost</option>
            </select>
          </label>
          <label>
            Estimated Value
            <input
              type="number"
              min="0"
              value={leadForm.estimated_value}
              onChange={(event) => setLeadForm((prev) => ({ ...prev, estimated_value: event.target.value }))}
            />
          </label>
          <label>
            Last Touch
            <input
              type="date"
              value={leadForm.last_touch}
              onChange={(event) => setLeadForm((prev) => ({ ...prev, last_touch: event.target.value }))}
            />
          </label>
          <label className="full">
            Notes
            <textarea
              rows="3"
              value={leadForm.notes}
              onChange={(event) => setLeadForm((prev) => ({ ...prev, notes: event.target.value }))}
            />
          </label>
          <button className="cta" disabled={busy} type="submit">
            {busy ? 'Saving...' : 'Create Lead'}
          </button>
        </form>
      </section>

      <section className="panel">
        <h2>Leads</h2>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Company</th>
                <th>Contact</th>
                <th>Stage</th>
                <th>Value</th>
                <th>Last Touch</th>
              </tr>
            </thead>
            <tbody>
              {leads.map((lead) => (
                <tr key={lead.id}>
                  <td>
                    <strong>{lead.company_name}</strong>
                    <small>#{lead.id}</small>
                  </td>
                  <td>{lead.contact_name}</td>
                  <td>
                    <span className={`tag ${lead.stage}`}>{lead.stage}</span>
                  </td>
                  <td>{toMoney(lead.estimated_value)}</td>
                  <td>{lead.last_touch || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <footer className="panel footer">
        <h2>Conversion Report Snapshot</h2>
        <p>
          <strong>{pipeline.find((item) => item.key === 'won').value}</strong> out of{' '}
          <strong>{leads.length}</strong> leads are closed-won this cycle.
        </p>
      </footer>
    </main>
  )
}

export default App
