import { useCallback, useEffect, useRef, useState } from 'react'
import { api, requestErrorMessage } from '../api/client'
import type { HouseAccess } from '../api/houseIntake'
import type { Access, EnrollmentSummary, Person, Program } from '../api/types'
import { capabilitiesFor } from '../api/types'

type ReviewerResponse = Person[] | { reviewers: Person[] }

const emptyAccess: Access = { username: '', manager: false }

export function useAppData() {
  const [access, setAccess] = useState<Access>(emptyAccess)
  const [houseAccess, setHouseAccess] = useState<HouseAccess | null>(null)
  const [assignments, setAssignments] = useState<EnrollmentSummary[]>([])
  const [programs, setPrograms] = useState<Program[]>([])
  const [reviewers, setReviewers] = useState<Person[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const loaded = useRef(false)

  const reload = useCallback(async () => {
    if (!loaded.current) setLoading(true)
    setError('')
    try {
      // A fragrance house account is fenced away from every household
      // endpoint on the server, so ask first which experience to load. A
      // failed probe falls back to the household experience: the server, not
      // this branch, is what keeps a house account out of household data.
      const house = await api
        .get<HouseAccess>('/house-intake/access')
        .then((response) => response.data)
        .catch(() => null)
      setHouseAccess(house)
      if (house?.house) {
        setAccess({ username: house.username, manager: false, house: house.house })
        loaded.current = true
        return
      }
      const [assignmentResponse, programResponse, reviewerResponse, accessResponse] =
        await Promise.all([
          api.get<EnrollmentSummary[]>('/calibration/enrollments'),
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
    // reload's setState calls run synchronously before its first await; this is
    // the standard fetch-on-mount pattern, not derived state being adjusted.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void reload()
  }, [reload])

  return {
    access,
    houseAccess,
    assignments,
    programs,
    reviewers,
    capabilities: capabilitiesFor(access, assignments),
    loading,
    error,
    reload,
  }
}
