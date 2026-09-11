import { useState } from 'react'

type ConfirmActionProps = {
  actionLabel: string
  confirmLabel: string
  description: string
  disabled?: boolean
  onConfirm: () => void
}

export function ConfirmAction({
  actionLabel,
  confirmLabel,
  description,
  disabled,
  onConfirm,
}: ConfirmActionProps) {
  const [confirming, setConfirming] = useState(false)

  if (!confirming)
    return (
      <button disabled={disabled} onClick={() => setConfirming(true)}>
        {actionLabel}
      </button>
    )

  return (
    <div className="confirm-action" role="group" aria-label={`Confirm ${actionLabel}`}>
      <p>{description}</p>
      <div className="button-row">
        <button
          disabled={disabled}
          onClick={() => {
            setConfirming(false)
            onConfirm()
          }}
        >
          {confirmLabel}
        </button>
        <button className="secondary" onClick={() => setConfirming(false)}>
          Cancel
        </button>
      </div>
    </div>
  )
}
