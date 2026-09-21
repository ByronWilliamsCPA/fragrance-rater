import { test, expect, type Route } from '@playwright/test'
import { mockApi, bootstrapRoutes, managerAccess } from './support/mock-api'

test.describe('Calibration entry routing', () => {
  test('opens the guided wizard on step 1 for a never-started enrollment', async ({ page }) => {
    await mockApi(page, {
      ...bootstrapRoutes(),
      '/calibration/enrollments': [
        {
          id: 'enr1',
          program_id: 'p1',
          reviewer_id: 'r1',
          revealed: false,
          has_started: false,
          total_presentations: 1,
          blotter_complete: 0,
          skin_planned: 0,
          skin_complete: 0,
          program_name: 'Baseline',
          program_version: '1',
        },
      ],
      '/calibration/enrollments/enr1': {
        id: 'enr1',
        program_id: 'p1',
        reviewer_id: 'r1',
        revealed: false,
        reveal_eligible: false,
        reveal_blocker: 'SKIN_PLAN',
        skin_plan_locked: false,
        presentations: [
          {
            id: 'samp1',
            session_id: 'sess1',
            blind_code: 'ABC-123',
            position: 1,
            skin_planned: false,
            blotter_locked: false,
            skin_locked: false,
            observations: [],
          },
        ],
      },
    })

    await page.goto('/calibration')

    await expect(page.getByRole('heading', { name: 'Guided calibration' })).toBeVisible()
    await expect(page.getByText(/Step 1 of/)).toBeVisible()
    await expect(page.getByRole('button', { name: 'Finalize skin-test plan' })).toBeVisible()
  })

  test('opens the guided wizard on the correct next step for an in-progress enrollment', async ({
    page,
  }) => {
    await mockApi(page, {
      ...bootstrapRoutes(),
      '/calibration/enrollments': [
        {
          id: 'enr1',
          program_id: 'p1',
          reviewer_id: 'r1',
          revealed: false,
          has_started: true,
          total_presentations: 1,
          blotter_complete: 0,
          skin_planned: 0,
          skin_complete: 0,
          program_name: 'Baseline',
          program_version: '1',
        },
      ],
      '/calibration/enrollments/enr1': {
        id: 'enr1',
        program_id: 'p1',
        reviewer_id: 'r1',
        revealed: false,
        reveal_eligible: false,
        reveal_blocker: 'BLOTTER',
        skin_plan_locked: true,
        presentations: [
          {
            id: 'samp1',
            session_id: 'sess1',
            blind_code: 'ABC-123',
            position: 1,
            skin_planned: false,
            blotter_locked: false,
            skin_locked: false,
            observations: [],
          },
        ],
      },
    })

    await page.goto('/calibration')

    await expect(page.getByRole('heading', { name: 'Guided calibration' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'ABC-123' })).toBeVisible()
    await expect(page.getByText('Blind observation')).toBeVisible()
  })

  test('shows the choice screen, self-assign only for a manager', async ({ page }) => {
    await mockApi(page, {
      ...bootstrapRoutes(managerAccess),
      '/calibration/enrollments': [
        {
          id: 'enr1',
          program_id: 'p1',
          reviewer_id: 'r1',
          revealed: true,
          has_started: true,
          total_presentations: 1,
          blotter_complete: 1,
          skin_planned: 0,
          skin_complete: 0,
          program_name: 'Baseline',
          program_version: '1',
        },
      ],
      '/calibration/programs': [
        { id: 'p1', name: 'Baseline', version: '1', status: 'active' },
        { id: 'p2', name: 'Retest round', version: '1', status: 'active' },
      ],
      '/calibration/programs/p2/members': [{ id: 'm1', group_name: 'Skin Retest' }],
    })

    await page.goto('/calibration')

    await expect(page.getByRole('heading', { name: 'Your calibration' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Redo "Skin Retest"' })).toBeVisible()
  })

  test('a deep link still bypasses routing entirely', async ({ page }) => {
    await mockApi(page, {
      ...bootstrapRoutes(),
      '/calibration/enrollments/enr1': (route: Route) =>
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 'enr1',
            program_id: 'p1',
            reviewer_id: 'r1',
            revealed: false,
            reveal_eligible: false,
            reveal_blocker: 'BLOTTER',
            skin_plan_locked: true,
            presentations: [
              {
                id: 'samp1',
                session_id: 'sess1',
                blind_code: 'ABC-123',
                position: 1,
                skin_planned: false,
                blotter_locked: false,
                skin_locked: false,
                observations: [],
              },
            ],
          }),
        }),
    })

    await page.goto('/calibration?assignment=enr1')

    await expect(page.getByLabel('Evaluator and program')).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Guided calibration' })).toHaveCount(0)
  })
})
