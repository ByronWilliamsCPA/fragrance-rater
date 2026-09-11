import { useEffect, useState } from 'react'
import axios from 'axios'
import './App.css'

const api = axios.create({ baseURL: `${import.meta.env.VITE_API_URL || '/api'}/v1` })
type Assignment = { id: string; program_id: string; reviewer_id: string }
type Observation = {
  id: string
  phase: string
  stage: string
  elapsed_minutes: number
  liking: number | null
  comments: string | null
}
type Sample = {
  id: string
  session_id: string
  blind_code: string
  position: number
  skin_planned: boolean
  blotter_locked: boolean
  skin_locked: boolean
  identity?: { name: string; brand: string; concentration: string }
  observations: Observation[]
}
type Enrollment = Assignment & {
  revealed: boolean
  skin_plan_locked: boolean
  presentations: Sample[]
}
type Person = { id: string; name: string }
type Program = Person & { version: string; status: string }
const dimensions = [
  'confidence',
  'sweetness',
  'freshness',
  'density',
  'familiarity',
  'dryness',
  'clean_soapy',
  'earthy_rooty',
  'bodily_animalic',
  'discomfort',
]

function App() {
  const [page, setPage] = useState('Calibration')
  const [catalog, setCatalog] = useState<(Person & { brand: string; concentration: string })[]>([])
  const [catalogQuery, setCatalogQuery] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [manager, setManager] = useState(false)
  const [assignments, setAssignments] = useState<Assignment[]>([])
  const [programs, setPrograms] = useState<Program[]>([])
  const [reviewers, setReviewers] = useState<Person[]>([])
  const [enrollment, setEnrollment] = useState<Enrollment | null>(null)
  const [selected, setSelected] = useState('')
  const [stage, setStage] = useState('BLOTTER')
  const [detected, setDetected] = useState('')
  const [programId, setProgramId] = useState('')
  const [history, setHistory] = useState<
    { id: string; fragrance_id: string; rating: number; evaluated_at: string }[]
  >([])
  const sample = enrollment?.presentations.find((p) => p.id === selected)
  function fail(e: unknown) {
    const detail = axios.isAxiosError(e) ? e.response?.data?.detail : undefined
    setError(typeof detail === 'string' ? detail : 'Request failed. Check your values and access.')
  }
  async function act(fn: () => Promise<void>) {
    setBusy(true)
    setError('')
    setNotice('')
    try {
      await fn()
    } catch (e) {
      fail(e)
    } finally {
      setBusy(false)
    }
  }
  async function refresh(id = enrollment?.id) {
    if (id) setEnrollment((await api.get(`/calibration/enrollments/${id}`)).data)
  }
  async function load() {
    const [a, p, r, c] = await Promise.all([
      api.get('/calibration/enrollments'),
      api.get('/calibration/programs'),
      api.get('/reviewers'),
      api.get('/calibration/access'),
    ])
    setAssignments(a.data)
    setPrograms(p.data)
    setReviewers(r.data.reviewers || r.data)
    setManager(c.data.manager)
  }
  useEffect(() => {
    void load().catch(fail)
  }, [])
  const scale = (name: string, max: number, disabled = false) => (
    <label key={name}>
      {name.replace(/_/g, ' ')}
      <select name={name} defaultValue="" disabled={disabled}>
        <option value="">Unanswered</option>
        {Array.from({ length: max + 1 }, (_, i) => (
          <option key={i} value={i}>
            {i}
          </option>
        ))}
      </select>
    </label>
  )
  async function searchCatalog() {
    setCatalog((await api.get('/fragrances', { params: { q: catalogQuery, limit: 100 } })).data)
  }
  async function save(form: HTMLFormElement) {
    if (!sample) return
    const values = Object.fromEntries(new FormData(form))
    const data: Record<string, unknown> = {
      stage,
      elapsed_minutes: Number(values.elapsed_minutes || 0),
      detected: detected === '' ? null : detected === 'yes',
    }
    for (const name of [
      'liking',
      'intensity',
      ...dimensions,
      'opening_liking',
      'drydown_liking',
      'would_wear',
      'would_buy',
      'artistic_appreciation',
      'projection',
      'longevity_minutes',
    ])
      data[name] = !values[name] ? null : Number(values[name])
    if (detected === 'no') {
      data.intensity = 0
      data.liking = null
    }
    for (const name of ['likes', 'dislikes', 'reminds_me_of', 'comments'])
      data[name] = values[name] || null
    data.perceived_notes = values.perceived_notes
      ? String(values.perceived_notes)
          .split(',')
          .map((x) => x.trim())
          .filter(Boolean)
      : null
    await api.post(
      `/calibration/presentations/${sample.id}/${sample.identity ? 'post-reveal' : 'observations'}`,
      data
    )
    form.reset()
    setDetected('')
    await refresh()
    setNotice('Observation saved. Original responses are retained.')
  }
  return (
    <div className="app">
      <header>
        <div className="eyebrow">PERSONAL SCENT JOURNAL</div>
        <h1>Fragrance Rater</h1>
        <p>Explore your preferences, one encounter at a time.</p>
      </header>
      <nav aria-label="Main navigation">
        {['Calibration', 'My Ratings', ...(manager ? ['Program setup'] : [])].map((p) => (
          <button key={p} aria-current={page === p ? 'page' : undefined} onClick={() => setPage(p)}>
            {p}
          </button>
        ))}
      </nav>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {notice && (
        <p role="status" className="notice">
          {notice}
        </p>
      )}
      <main>
        {page === 'Calibration' && (
          <>
            <section>
              <h2>Your calibration</h2>
              <p>
                Use the code on your sample. Identities appear after required blind evaluations are
                locked.
              </p>
              <label>
                Evaluator and program
                <select
                  value={enrollment?.id || ''}
                  onChange={(e) => {
                    setSelected('')
                    void act(() => refresh(e.target.value))
                  }}
                >
                  <option value="">Choose assignment</option>
                  {assignments.map((a) => (
                    <option key={a.id} value={a.id}>
                      {reviewers.find((r) => r.id === a.reviewer_id)?.name || a.reviewer_id} ·{' '}
                      {programs.find((p) => p.id === a.program_id)?.name || 'Program'}
                    </option>
                  ))}
                </select>
              </label>
            </section>
            {enrollment && (
              <div className="workspace">
                <aside>
                  <h2>Sessions</h2>
                  <p>
                    {enrollment.presentations.filter((p) => p.blotter_locked).length} /{' '}
                    {enrollment.presentations.length} screens locked
                  </p>
                  {Array.from(new Set(enrollment.presentations.map((p) => p.session_id))).map(
                    (id, i) => (
                      <div key={id}>
                        <h3>Session {i + 1}</h3>
                        {enrollment.presentations
                          .filter((p) => p.session_id === id)
                          .map((p) => (
                            <button
                              className="sample"
                              key={p.id}
                              aria-pressed={selected === p.id}
                              onClick={() => {
                                setSelected(p.id)
                                setStage('BLOTTER')
                                setDetected('')
                              }}
                            >
                              {p.blind_code}
                              <small>{p.blotter_locked ? 'Locked' : 'Open'}</small>
                            </button>
                          ))}
                      </div>
                    )
                  )}
                  <button
                    disabled={busy || enrollment.skin_plan_locked}
                    onClick={() =>
                      void act(async () => {
                        await api.post(`/calibration/enrollments/${enrollment.id}/lock-skin-plan`)
                        await refresh()
                      })
                    }
                  >
                    Finalize skin-test plan
                  </button>
                  <button
                    disabled={busy || enrollment.revealed}
                    onClick={() =>
                      void act(async () => {
                        await api.post(`/calibration/enrollments/${enrollment.id}/reveal`)
                        await refresh()
                      })
                    }
                  >
                    Reveal completed baseline
                  </button>
                </aside>
                <section>
                  {sample ? (
                    <>
                      <div className="eyebrow">SAMPLE {sample.position}</div>
                      <h2>{sample.blind_code}</h2>
                      {sample.identity && (
                        <p className="notice">
                          {sample.identity.brand} · {sample.identity.name} ·{' '}
                          {sample.identity.concentration}
                        </p>
                      )}
                      <label>
                        Stage
                        <select value={stage} onChange={(e) => setStage(e.target.value)}>
                          <option value="BLOTTER">Blotter screen</option>
                          {sample.skin_planned && <option value="SKIN">Skin test</option>}
                        </select>
                      </label>
                      {!sample.skin_planned && !enrollment.skin_plan_locked && (
                        <form
                          onSubmit={(e) => {
                            e.preventDefault()
                            const reason = String(new FormData(e.currentTarget).get('reason'))
                            void act(async () => {
                              await api.post(`/calibration/presentations/${sample.id}/skin-plan`, {
                                reason,
                              })
                              await refresh()
                            })
                          }}
                        >
                          <label>
                            Reason to add a skin test
                            <input
                              name="reason"
                              required
                              placeholder="For example: low confidence"
                            />
                          </label>
                          <button disabled={busy}>Plan skin test</button>
                        </form>
                      )}
                      <form
                        key={`${sample.id}-${stage}`}
                        onSubmit={(e) => {
                          e.preventDefault()
                          const form = e.currentTarget
                          void act(() => save(form))
                        }}
                      >
                        <fieldset
                          disabled={
                            busy ||
                            (!sample.identity &&
                              (stage === 'BLOTTER' ? sample.blotter_locked : sample.skin_locked))
                          }
                        >
                          <legend>
                            {sample.identity ? 'Post-reveal observation' : 'Blind observation'}
                          </legend>
                          <div className="fields">
                            <label>
                              Elapsed minutes
                              <input
                                name="elapsed_minutes"
                                type="number"
                                min="0"
                                defaultValue="0"
                              />
                            </label>
                            <label>
                              Detected
                              <select
                                value={detected}
                                onChange={(e) => setDetected(e.target.value)}
                              >
                                <option value="">Unanswered</option>
                                <option value="yes">Yes</option>
                                <option value="no">No</option>
                              </select>
                            </label>
                            {scale('intensity', 5, detected === 'no')}
                            {scale('liking', 10, detected === 'no')}
                            {dimensions.map((d) => scale(d, 5))}
                          </div>
                          {detected === 'no' && (
                            <p>Intensity will be saved as 0; liking will remain unanswered.</p>
                          )}
                          {stage === 'SKIN' && (
                            <div className="fields">
                              {[
                                'opening_liking',
                                'drydown_liking',
                                'would_wear',
                                'would_buy',
                                'artistic_appreciation',
                              ].map((d) => scale(d, 10))}
                              {scale('projection', 5)}
                              <label>
                                Longevity (minutes)
                                <input name="longevity_minutes" type="number" min="0" />
                              </label>
                            </div>
                          )}
                          <label>
                            Perceived notes
                            <input
                              name="perceived_notes"
                              placeholder="Your own words, separated by commas"
                            />
                          </label>
                          {['likes', 'dislikes', 'reminds_me_of', 'comments'].map((n) => (
                            <label key={n}>
                              {n.replace(/_/g, ' ')}
                              <textarea name={n} rows={2} />
                            </label>
                          ))}
                          <button>Save observation</button>
                        </fieldset>
                      </form>
                      {!sample.identity && (
                        <button
                          disabled={
                            busy ||
                            (stage === 'BLOTTER' ? sample.blotter_locked : sample.skin_locked)
                          }
                          onClick={() =>
                            void act(async () => {
                              await api.post(
                                `/calibration/presentations/${sample.id}/lock/${stage}`
                              )
                              await refresh()
                            })
                          }
                        >
                          Lock {stage.toLowerCase()} responses
                        </button>
                      )}
                      <h3>Saved observations</h3>
                      {sample.observations.length ? (
                        sample.observations.map((o) => (
                          <article key={o.id}>
                            <strong>
                              {o.stage} · {o.elapsed_minutes} min · {o.phase.replace(/_/g, ' ')}
                            </strong>
                            <p>
                              Liking: {o.liking ?? 'Unanswered'}
                              {o.comments ? ` · ${o.comments}` : ''}
                            </p>
                          </article>
                        ))
                      ) : (
                        <p>No observations yet.</p>
                      )}
                    </>
                  ) : (
                    <p>Select a sample to begin.</p>
                  )}
                </section>
              </div>
            )}
          </>
        )}
        {page === 'My Ratings' && (
          <section>
            <h2>Ordinary encounters</h2>
            <label>
              Search fragrances
              <input
                value={catalogQuery}
                onChange={(e) => setCatalogQuery(e.target.value)}
                placeholder="Fragrance or house"
              />
            </label>
            <button disabled={busy} onClick={() => void act(searchCatalog)}>
              Search catalog
            </button>
            <p>Each submission adds a dated encounter. Earlier ratings remain in history.</p>
            <form
              onSubmit={(e) => {
                e.preventDefault()
                const values = Object.fromEntries(new FormData(e.currentTarget))
                void act(async () => {
                  await api.post('/evaluations', {
                    ...values,
                    rating: Number(values.rating),
                    evaluated_at: values.evaluated_at
                      ? new Date(String(values.evaluated_at)).toISOString()
                      : null,
                  })
                  setHistory(
                    (await api.get('/evaluations', { params: { reviewer_id: values.reviewer_id } }))
                      .data
                  )
                  setNotice('New encounter saved.')
                })
              }}
            >
              <label>
                Evaluator
                <select
                  name="reviewer_id"
                  required
                  onChange={(e) =>
                    void act(async () =>
                      setHistory(
                        (await api.get('/evaluations', { params: { reviewer_id: e.target.value } }))
                          .data
                      )
                    )
                  }
                >
                  <option value="">Choose evaluator</option>
                  {reviewers.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Fragrance version
                <select name="fragrance_id" required>
                  <option value="">Search and choose a fragrance</option>
                  {catalog.map((f) => (
                    <option key={f.id} value={f.id}>
                      {f.brand} · {f.name} · {f.concentration}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Rating (1–5)
                <input name="rating" type="number" min="1" max="5" required />
              </label>
              <label>
                Encounter date (optional)
                <input name="evaluated_at" type="datetime-local" />
              </label>
              <label>
                Observations
                <textarea name="notes" />
              </label>
              <button disabled={busy}>Save new encounter</button>
            </form>
            <h3>Encounter history</h3>
            {history.map((h) => (
              <article key={h.id}>
                <strong>
                  {catalog.find((f) => f.id === h.fragrance_id)?.name || 'Saved fragrance'} ·{' '}
                  {h.rating}/5
                </strong>
                <p>{h.evaluated_at} UTC</p>
              </article>
            ))}
          </section>
        )}
        {page === 'Program setup' && manager && (
          <section>
            <h2>Program setup</h2>
            <p>Use exact catalog version IDs. Evaluators should use the Calibration area.</p>
            <form
              onSubmit={(e) => {
                e.preventDefault()
                const values = Object.fromEntries(new FormData(e.currentTarget))
                void act(async () => {
                  const p = await api.post('/calibration/programs', values)
                  setProgramId(p.data.id)
                  await load()
                  setNotice('Draft created.')
                })
              }}
            >
              <label>
                Name
                <input name="name" required />
              </label>
              <label>
                Version
                <input name="version" required />
              </label>
              <button disabled={busy}>Create draft</button>
            </form>
            <label>
              Program
              <select value={programId} onChange={(e) => setProgramId(e.target.value)}>
                <option value="">Choose program</option>
                {programs.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} · {p.version} · {p.status}
                  </option>
                ))}
              </select>
            </label>
            <form
              onSubmit={(e) => {
                e.preventDefault()
                const values = Object.fromEntries(new FormData(e.currentTarget))
                void act(async () => {
                  const m = await api.post(`/calibration/programs/${programId}/members`, {
                    ...values,
                    repeat_of_id: values.repeat_of_id || null,
                  })
                  setNotice(`Member added: ${m.data.id}. Use this ID to link a repeat.`)
                })
              }}
            >
              <label>
                Fragrance catalog version ID
                <input name="fragrance_id" required />
              </label>
              <label>
                Role
                <select name="role">
                  {[
                    'UNIVERSAL_BASELINE',
                    'HIDDEN_REPEAT',
                    'HOLDOUT',
                    'ACTIVE_LEARNING',
                    'RETEST',
                    'OWNED_VALIDATION',
                    'OTHER',
                  ].map((r) => (
                    <option key={r}>{r}</option>
                  ))}
                </select>
              </label>
              <label>
                Original membership ID (repeats only)
                <input name="repeat_of_id" />
              </label>
              <label>
                Version verification evidence
                <textarea name="identity_evidence" required />
              </label>
              <button disabled={busy || !programId}>Add member</button>
            </form>
            <button
              disabled={busy || !programId}
              onClick={() =>
                void act(async () => {
                  await api.post(`/calibration/programs/${programId}/activate`)
                  await load()
                  setNotice('Definition locked.')
                })
              }
            >
              Activate and lock definition
            </button>
            <form
              onSubmit={(e) => {
                e.preventDefault()
                const values = Object.fromEntries(new FormData(e.currentTarget))
                void act(async () => {
                  await api.post(`/calibration/programs/${programId}/enroll`, {
                    reviewer_id: values.reviewer_id,
                    recorder_usernames: String(values.recorders)
                      .split(',')
                      .map((x) => x.trim()),
                    session_size: Number(values.session_size),
                  })
                  await load()
                  setNotice('Evaluator enrolled; blind codes generated.')
                })
              }}
            >
              <label>
                Evaluator
                <select name="reviewer_id" required>
                  {reviewers.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Authorized recorder usernames
                <input name="recorders" required placeholder="Comma-separated usernames" />
              </label>
              <label>
                Samples per session
                <input name="session_size" type="number" min="1" max="20" defaultValue="3" />
              </label>
              <button disabled={busy || !programId}>Enroll evaluator</button>
            </form>
          </section>
        )}
      </main>
      <footer>Ordinary encounters and controlled observations share one preference history.</footer>
    </div>
  )
}
export default App
