type FeedbackBannerProps = {
  error?: string
  notice?: string
}

export function FeedbackBanner({ error, notice }: FeedbackBannerProps) {
  return (
    <>
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
    </>
  )
}
