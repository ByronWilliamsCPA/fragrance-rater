import axios from 'axios'
import { useState } from 'react'
import { api } from '../api/client'
import type { Person } from '../api/types'
import type { useTask } from '../hooks/useTask'

const EVALUATOR_NAME_MAX = 100

/**
 * Manager form: add a new evaluator so they can be enrolled.
 *
 * Shared by the family pilot page and the advanced setup page, which each own
 * the `useTask` that reports its outcome. `reload` must resolve only after the
 * refreshed reviewer list is committed (the parent's `reload` does), so the
 * `onAdded` callback can rely on the new person already being listed.
 */
export function AddEvaluatorForm({
  task,
  reload,
  onAdded,
}: {
  task: ReturnType<typeof useTask>
  reload: () => Promise<void>
  onAdded?: (person: Person) => void
}) {
  const [name, setName] = useState('')

  async function addEvaluator() {
    const trimmed = name.trim()
    if (trimmed.length < 1 || trimmed.length > EVALUATOR_NAME_MAX) {
      task.setError(`Enter the evaluator's name, 1 to ${EVALUATOR_NAME_MAX} characters.`)
      return
    }
    let created: Person
    try {
      created = (await api.post<Person>('/reviewers', { name: trimmed })).data
    } catch (reason) {
      // Only the duplicate-name conflict gets its own wording; the server's
      // message repeats the submitted name, so it is not shown. Anything else
      // goes through the shared request-error handling in useTask.
      if (axios.isAxiosError(reason) && reason.response?.status === 409) {
        task.setError('That name is already in use. Choose a different name.')
        return
      }
      throw reason
    }
    // #ASSUME: timing-dependencies: the parent's reload() resolves only after
    // the refreshed reviewers prop is committed, so the new option exists
    // before onAdded selects it.
    // #VERIFY: if the option were missing, a controlled select would fall back
    // to its empty entry and the manager would pick by hand.
    await reload()
    setName('')
    onAdded?.(created)
    task.setNotice('Evaluator added. They can now be enrolled below.')
  }

  return (
    <form
      aria-labelledby="add-evaluator-heading"
      onSubmit={(event) => {
        event.preventDefault()
        void task.run(addEvaluator)
      }}
    >
      <h4 id="add-evaluator-heading">Add an evaluator</h4>
      <p id="add-evaluator-hint">
        A new person must be added here before they can be enrolled below.
      </p>
      <label>
        Evaluator name
        <input
          name="new_evaluator_name"
          value={name}
          maxLength={EVALUATOR_NAME_MAX}
          aria-describedby="add-evaluator-hint"
          required
          onChange={(event) => setName(event.target.value)}
        />
      </label>
      <button disabled={task.busy}>Add evaluator</button>
    </form>
  )
}
