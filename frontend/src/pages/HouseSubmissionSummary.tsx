import { Fragment } from 'react'
import {
  availabilityOptions,
  concentrationOptions,
  labelFor,
  marketedForOptions,
  permissionOptions,
  pyramidTiers,
  type HouseSubmissionPayload,
} from '../api/houseIntake'

type Props = {
  house: string
  payload: HouseSubmissionPayload
}

function List({ items }: { items: string[] }) {
  if (!items.length) return <>Not given</>
  return (
    <ol className="summary-list">
      {items.map((item, index) => (
        <li key={`${index}-${item}`}>{item}</li>
      ))}
    </ol>
  )
}

function text(value: string | number | null): string {
  return value === null || value === '' ? 'Not given' : String(value)
}

/**
 * Everything a house said, in the order the form asked it. Shown before the
 * house submits ("check your answers") and afterwards as the record itself,
 * so what they confirmed and what we store read identically.
 */
export function HouseSubmissionSummary({ house, payload }: Props) {
  const concentration =
    payload.concentration === 'OTHER'
      ? text(payload.concentration_other)
      : labelFor(concentrationOptions, payload.concentration)
  const permission = permissionOptions.find((option) => option.value === payload.permission_scope)

  return (
    <div className="house-summary">
      <h4>The fragrance</h4>
      <dl className="standing">
        <dt>Name</dt>
        <dd>{payload.fragrance_name}</dd>
        <dt>House</dt>
        <dd>{house}</dd>
        <dt>Collection or line</dt>
        <dd>{text(payload.line)}</dd>
        <dt>Concentration</dt>
        <dd>{concentration}</dd>
        <dt>Formulation or edition</dt>
        <dd>{text(payload.version_label)}</dd>
        <dt>Launch year</dt>
        <dd data-numeric>{text(payload.launch_year)}</dd>
        <dt>Availability</dt>
        <dd>{labelFor(availabilityOptions, payload.availability)}</dd>
        <dt>Marketed for</dt>
        <dd>{labelFor(marketedForOptions, payload.marketed_for)}</dd>
        <dt>Perfumers</dt>
        <dd>
          <List items={payload.perfumers} />
        </dd>
        <dt>Product page</dt>
        <dd>
          {/* Only https:// addresses are ever stored (schema validator). */}
          {payload.product_url ? (
            <a href={payload.product_url} rel="noopener noreferrer nofollow" target="_blank">
              {payload.product_url}
            </a>
          ) : (
            'Not given'
          )}
        </dd>
        <dt>Barcodes</dt>
        <dd data-numeric>
          <List items={payload.gtins} />
        </dd>
      </dl>

      <h4>The scent, in the house&rsquo;s words</h4>
      <dl className="standing">
        {payload.note_structure === 'pyramid' ? (
          pyramidTiers.map((tier) => (
            <Fragment key={tier.position}>
              <dt>{tier.label}</dt>
              <dd>
                <List
                  items={payload.notes
                    .filter((note) => note.position === tier.position)
                    .map((note) => note.text)}
                />
              </dd>
            </Fragment>
          ))
        ) : (
          <>
            <dt>Notes (no pyramid)</dt>
            <dd>
              <List items={payload.notes.map((note) => note.text)} />
            </dd>
          </>
        )}
        <dt>Accords</dt>
        <dd>
          <List items={payload.accords} />
        </dd>
        <dt>Family</dt>
        <dd>{text(payload.family_as_described)}</dd>
        <dt>Description</dt>
        <dd className="house-summary__description">{text(payload.description)}</dd>
      </dl>

      <h4>Permission</h4>
      <dl className="standing">
        <dt>Use</dt>
        <dd>{permission?.label ?? 'Not given'}</dd>
        <dt>Provided by</dt>
        <dd>
          {text(payload.contact_name)}
          {payload.contact_role ? `, ${payload.contact_role}` : ''}
        </dd>
        <dt>Authority confirmed</dt>
        <dd>{payload.attested ? 'Yes' : 'Not yet'}</dd>
        <dt>Note to the reviewer</dt>
        <dd>{text(payload.note_to_reviewer)}</dd>
      </dl>
    </div>
  )
}
