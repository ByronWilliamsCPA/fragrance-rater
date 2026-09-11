import { useState } from 'react'
import { requestErrorMessage } from '../api/client'

export function useTask() {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  async function run(action: () => Promise<void>) {
    setBusy(true)
    setError('')
    setNotice('')
    try {
      await action()
    } catch (reason) {
      setError(requestErrorMessage(reason))
    } finally {
      setBusy(false)
    }
  }

  return { busy, error, notice, setError, setNotice, run }
}
