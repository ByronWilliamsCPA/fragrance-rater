import { useRef, useState } from 'react'
import { requestErrorMessage } from '../api/client'

export function useTask() {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const activeRuns = useRef(0)

  async function run(action: () => Promise<void>) {
    activeRuns.current += 1
    setBusy(true)
    setError('')
    setNotice('')
    try {
      await action()
    } catch (reason) {
      setError(requestErrorMessage(reason))
    } finally {
      activeRuns.current -= 1
      if (activeRuns.current === 0) setBusy(false)
    }
  }

  return { busy, error, notice, setError, setNotice, run }
}
