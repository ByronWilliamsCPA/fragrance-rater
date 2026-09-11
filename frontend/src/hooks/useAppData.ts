import { useCallback, useEffect, useRef, useState } from 'react'
import { api, requestErrorMessage } from '../api/client'
import type { Access, Assignment, Person, Program } from '../api/types'
import { capabilitiesFor } from '../api/types'

type ReviewerResponse = Person[] | { reviewers: Person[] }

const emptyAccess: Access = { username: '', manager: false }

export function useAppData() {
  const [access, setAccess] = useState<Access>(emptyAccess)
  const [assignments, setAssignments] = useState<Assignment[]>([])
  const [programs, setPrograms] = useState<Program[]>([])
  const [reviewers, setReviewers] = useState<Person[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const loaded = useRef(false)

  const reload = useCallback(async () => {
    if (!loaded.current) setLoading(true)
    setError('')
    try {
      const [assignmentResponse, programResponse, reviewerResponse, accessResponse] =
        await Promise.all([
          api.get<Assignment[]>('/calibration/enrollments'),
          api.get<Program[]>('/calibration/programs'),
          api.get<ReviewerResponse>('/reviewers'),
          api.get<Access>('/calibration/access'),
        ])
      setAssignments(assignmentResponse.data)
      setPrograms(programResponse.data)
      setReviewers(
        Array.isArray(reviewerResponse.data)
          ? reviewerResponse.data
          : reviewerResponse.data.reviewers
      )
      setAccess(accessResponse.data)
      loaded.current = true
    } catch (reason) {
      setError(requestErrorMessage(reason))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void reload()
  }, [reload])

  return {
    access,
    assignments,
    programs,
    reviewers,
    capabilities: capabilitiesFor(access, assignments),
    loading,
    error,
    reload,
  }
}
