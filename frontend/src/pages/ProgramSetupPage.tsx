import { useState } from 'react'
import { api } from '../api/client'
import type { Person, Program } from '../api/types'
import { ConfirmAction } from '../components/ConfirmAction'
import { EmptyState } from '../components/PageState'
import { FeedbackBanner } from '../components/FeedbackBanner'
import { useTask } from '../hooks/useTask'

type ProgramSetupPageProps = {
  programs: Program[]
  reviewers: Person[]
  reload: () => Promise<void>
}

const roles = [
  'UNIVERSAL_BASELINE',
  'HIDDEN_REPEAT',
  'HOLDOUT',
  'ACTIVE_LEARNING',
  'RETEST',
  'OWNED_VALIDATION',
  'OTHER',
]

export function ProgramSetupPage({ programs, reviewers, reload }: ProgramSetupPageProps) {
  const [programId, setProgramId] = useState('')
  const task = useTask()

  async function createProgram(form: HTMLFormElement) {
    const values = Object.fromEntries(new FormData(form))
    const response = await api.post<{ id: string }>('/calibration/programs', values)
    setProgramId(response.data.id)
    await reload()
    form.reset()
    task.setNotice('Draft created.')
  }

  async function addMember(form: HTMLFormElement) {
    const values = Object.fromEntries(new FormData(form))
    const response = await api.post<{ id: string }>(`/calibration/programs/${programId}/members`, {
      ...values,
      repeat_of_id: values.repeat_of_id || null,
    })
    form.reset()
    task.setNotice(`Member added: ${response.data.id}. Use this ID to link a repeat.`)
  }

  async function activate() {
    await api.post(`/calibration/programs/${programId}/activate`)
    await reload()
    task.setNotice('Definition locked.')
  }

  async function enroll(form: HTMLFormElement) {
    const values = Object.fromEntries(new FormData(form))
    await api.post(`/calibration/programs/${programId}/enroll`, {
      reviewer_id: values.reviewer_id,
      recorder_usernames: String(values.recorders)
        .split(',')
        .map((username) => username.trim())
        .filter(Boolean),
      session_size: Number(values.session_size),
    })
    await reload()
    form.reset()
    task.setNotice('Evaluator enrolled; blind codes generated.')
  }

  return (
    <section>
      <div className="page-heading">
        <div>
          <div className="eyebrow">MANAGER</div>
          <h2>Program setup</h2>
        </div>
        <span className="status-chip">Restricted</span>
      </div>
      <p>Use exact catalog version IDs. Evaluators should use the Calibration area.</p>
      <FeedbackBanner error={task.error} notice={task.notice} />
      <form
        onSubmit={(event) => {
          event.preventDefault()
          const form = event.currentTarget
          void task.run(() => createProgram(form))
        }}
      >
        <div className="fields fields-compact">
          <label>
            Name
            <input name="name" required />
          </label>
          <label>
            Version
            <input name="version" required />
          </label>
        </div>
        <button disabled={task.busy}>Create draft</button>
      </form>
      {programs.length ? (
        <>
          <label>
            Program
            <select value={programId} onChange={(event) => setProgramId(event.target.value)}>
              <option value="">Choose program</option>
              {programs.map((program) => (
                <option key={program.id} value={program.id}>
                  {program.name} · {program.version} · {program.status}
                </option>
              ))}
            </select>
          </label>
          <form
            onSubmit={(event) => {
              event.preventDefault()
              const form = event.currentTarget
              void task.run(() => addMember(form))
            }}
          >
            <label>
              Fragrance catalog version ID
              <input name="fragrance_id" required />
            </label>
            <label>
              Role
              <select name="role">
                {roles.map((role) => (
                  <option key={role}>{role}</option>
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
            <button disabled={task.busy || !programId}>Add member</button>
          </form>
          <ConfirmAction
            actionLabel="Activate and lock definition"
            confirmLabel="Confirm activation"
            description="Activation freezes the program definition. Review every exact version, role, and repeat before continuing."
            disabled={task.busy || !programId}
            onConfirm={() => void task.run(activate)}
          />
          <form
            onSubmit={(event) => {
              event.preventDefault()
              const form = event.currentTarget
              void task.run(() => enroll(form))
            }}
          >
            <label>
              Evaluator
              <select name="reviewer_id" required>
                <option value="">Choose evaluator</option>
                {reviewers.map((reviewer) => (
                  <option key={reviewer.id} value={reviewer.id}>
                    {reviewer.name}
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
            <button disabled={task.busy || !programId}>Enroll evaluator</button>
          </form>
        </>
      ) : (
        <EmptyState title="No programs yet">Create a draft to begin program setup.</EmptyState>
      )}
    </section>
  )
}
